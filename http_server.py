import logging
import os
from aiohttp import web

logger = logging.getLogger(__name__)

class HTTPServer:
    def __init__(self, twitter_bot):
        self.bot = twitter_bot
        self.http_app = None
        self.runner = None
        self.site = None

    async def health_check(self, request):
        """Health check endpoint for Koyeb"""
        return web.Response(text="Bot is running!")

    async def start_http_server(self):
        """Start HTTP server for health checks"""
        self.http_app = web.Application()
        self.http_app.router.add_get('/', self.health_check)
        self.http_app.router.add_get('/health', self.health_check)
        
        self.runner = web.AppRunner(self.http_app)
        await self.runner.setup()
        
        port = int(os.environ.get('PORT', 8000))
        self.site = web.TCPSite(self.runner, '0.0.0.0', port)
        await self.site.start()
        
        logger.info(f"HTTP server started on port {port}")
        return self.runner, self.site

    async def shutdown_server(self):
        """Shutdown HTTP server"""
        if self.runner:
            logger.info("Stopping HTTP server...")
            await self.runner.cleanup()
