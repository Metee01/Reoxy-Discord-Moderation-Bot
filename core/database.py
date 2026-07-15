"""
Reoxy Bot — Veritabanı Bağlantı Yöneticisi

Async PostgreSQL bağlantısı (asyncpg pool), tablo oluşturma ve bağlantı yaşam döngüsü.
"""

from __future__ import annotations

import os
import asyncpg
from loguru import logger

from database.models import ALL_TABLES, MIGRATIONS


class Database:
    """Async PostgreSQL veritabanı yöneticisi."""

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or os.getenv("DATABASE_URL")
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        """Aktif veritabanı havuzunu döndürür."""
        if self._pool is None:
            raise RuntimeError("Veritabanı havuzu henüz oluşturulmadı. connect() çağrılmalı.")
        return self._pool

    async def connect(self) -> None:
        """
        Veritabanı bağlantı havuzunu kurar ve tabloları oluşturur.
        """
        if not self.dsn:
            raise RuntimeError("DATABASE_URL çevre değişkeni (veya dsn parametresi) belirtilmedi.")

        # Supabase Session/Transaction Modu bağlantı sınırları ve asenkron bot çalışma
        # senaryoları için min_size=1 ve max_size=5 (veya max_size=2) idealdir.
        # Böylece "max clients reached" (EMAXCONNSESSION) hatasının önüne geçilir.
        self._pool = await asyncpg.create_pool(
            self.dsn,
            min_size=1,
            max_size=5,
            max_queries=50000,
            max_inactive_connection_lifetime=300.0
        )
        
        # Tabloları oluştur ve migrasyon uygula
        await self._create_tables()
        await self._apply_migrations()

        logger.info("Veritabanı bağlantı havuzu kuruldu.")

    async def _create_tables(self) -> None:
        """Tüm tabloları oluşturur (yoksa)."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for sql in ALL_TABLES:
                    await conn.execute(sql)
        logger.debug("Veritabanı tabloları kontrol edildi / oluşturuldu")

    async def _apply_migrations(self) -> None:
        """Mevcut tablolara yeni sütun ekler. Zaten varsa sessizce atlar."""
        applied = 0
        async with self.pool.acquire() as conn:
            for sql in MIGRATIONS:
                try:
                    async with conn.transaction():
                        await conn.execute(sql)
                    applied += 1
                except Exception:
                    pass  # Sütun zaten mevcut
        if applied > 0:
            logger.debug(f"{applied} migrasyon uygulandı")

    async def close(self) -> None:
        """Veritabanı bağlantı havuzunu kapatır."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Veritabanı bağlantı havuzu kapatıldı")

    async def execute(self, query: str, *params) -> str:
        """
        SQL sorgusu çalıştırır.

        Args:
            query: SQL sorgu string'i.
            params: Sorgu parametreleri.

        Returns:
            Komut durum string'i (örn. 'INSERT 0 1').
        """
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *params)

    async def fetch_one(self, query: str, *params) -> asyncpg.Record | None:
        """
        Tek satır döndüren sorgu çalıştırır.

        Args:
            query: SQL sorgu string'i.
            params: Sorgu parametreleri.

        Returns:
            Satır nesnesi veya None.
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *params)

    async def fetch_all(self, query: str, *params) -> list[asyncpg.Record]:
        """
        Tüm satırları döndüren sorgu çalıştırır.

        Args:
            query: SQL sorgu string'i.
            params: Sorgu parametreleri.

        Returns:
            Satır listesi.
        """
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *params)
