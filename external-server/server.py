"""Servidor externo ('internet' simulada): tres servicios en un proceso asyncio.

  - HTTP :8000       -> destino del tráfico web y de los curl de verificación
  - UDP  :10000      -> eco para el tráfico VoIP simulado
  - TCP  :9000       -> sumidero para el tráfico bulk (descarta lo recibido)

Solo biblioteca estándar: este contenedor no necesita dependencias.
"""
import asyncio


async def http_server():
    async def handle(reader, writer):
        try:
            await reader.readuntil(b"\r\n\r\n")
        except Exception:
            pass
        body = b"ok\n"
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode()
                     + b"\r\nConnection: close\r\n\r\n" + body)
        try:
            await writer.drain()
        finally:
            writer.close()
    srv = await asyncio.start_server(handle, "0.0.0.0", 8000)
    async with srv:
        await srv.serve_forever()


class UdpEcho(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.transport.sendto(data, addr)     # eco: permite medir RTT de "VoIP" extremo a extremo


async def bulk_sink():
    async def handle(reader, writer):
        try:
            while await reader.read(65536):
                pass
        except Exception:
            pass
        finally:
            writer.close()
    srv = await asyncio.start_server(handle, "0.0.0.0", 9000)
    async with srv:
        await srv.serve_forever()


async def main():
    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(UdpEcho, local_addr=("0.0.0.0", 10000))
    print("servidor externo: http:8000 udp-echo:10000 bulk-sink:9000")
    await asyncio.gather(http_server(), bulk_sink())


if __name__ == "__main__":
    asyncio.run(main())
