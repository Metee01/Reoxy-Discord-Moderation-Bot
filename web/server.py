"""
Reoxy Bot — Health Check Web Sunucusu

Render.com üzerinde Web Service olarak çalışabilmek için
gerekli minimal async HTTP sunucusu. Render, servisin
ayakta olduğunu anlamak için bu porta bağlantı yapar.
Zero ek bağımlılık — asyncio.start_server kullanır.
"""

from __future__ import annotations

import asyncio
import json
import os

from loguru import logger


class HealthServer:
    """Minimal async HTTP health check sunucusu."""

    def __init__(self, host: str = "0.0.0.0", port: int | None = None) -> None:
        self.host = host
        self.port = port or int(os.getenv("PORT", "10000"))
        self._server: asyncio.Server | None = None

    async def _handle_request(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Gelen HTTP isteklerini yanıtlar."""
        try:
            request_line = await reader.readline()
            if not request_line:
                writer.close()
                return

            _, path, _ = request_line.decode().strip().split(" ", 2)

            while True:
                header_line = await reader.readline()
                if header_line in (b"\r\n", b"\n", b""):
                    break

            if path in ("/", "/health"):
                body = json.dumps({
                    "status": "ok",
                    "service": "Reoxy Bot",
                }).encode()
                response = (
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                    b"Connection: close\r\n"
                    b"\r\n"
                    + body
                )
            else:
                body = b"Not Found"
                response = (
                    b"HTTP/1.1 404 Not Found\r\n"
                    b"Content-Type: text/plain\r\n"
                    b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                    b"Connection: close\r\n"
                    b"\r\n"
                    + body
                )

            writer.write(response)
            await writer.drain()
        except Exception as exc:
            logger.debug("Health check isteği işlenirken hata: {}", exc)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def start(self) -> None:
        """Sunucuyu başlatır ve arka planda çalıştırır."""
        self._server = await asyncio.start_server(
            self._handle_request, self.host, self.port
        )
        logger.info(
            "Health check sunucusu başlatıldı: {}:{}",
            self.host, self.port,
        )

    async def stop(self) -> None:
        """Sunucuyu durdurur."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Health check sunucusu durduruldu.")
