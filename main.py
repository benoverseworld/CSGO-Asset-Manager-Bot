#!/usr/bin/env python3
"""
CS:GO Asset Manager Bot - Main Entry Point
A sophisticated Discord bot for managing CS:GO assets, server configurations,
and team collaboration with advanced features.

Author: benoverseworld
Version: 2.1.0
License: MIT
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv
from loguru import logger

from bot.core.config import Config
from bot.core.database import DatabaseManager
from bot.core.cache import CacheManager
from bot.utils.error_handler import ErrorHandler
from services.steam_api.client import SteamAPIClient
from services.price_tracker.tracker import PriceTracker

# Load environment variables
load_dotenv()

# Configure logging
logger.add(
    "logs/bot_{time}.log",
    rotation="500 MB",
    retention="10 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} - {message}"
)


class CSGOAssetBot(commands.Bot):
    """
    Main bot class with enhanced functionality for CS:GO asset management.
    """
    
    def __init__(self):
        # Load configuration
        self.config = Config()
        
        # Initialize bot with intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix=self.config.get('discord.prefix', '!'),
            intents=intents,
            help_command=None
        )
        
        # Initialize managers
        self.db = None
        self.cache = None
        self.steam_client = None
        self.price_tracker = None
        self.error_handler = ErrorHandler(self)
        
        logger.info("Bot initialized successfully")
    
    async def setup_hook(self):
        """
        Setup hook called before the bot starts.
        Initializes all services and loads cogs.
        """
        logger.info("Starting bot setup...")
        
        try:
            # Initialize database connection
            self.db = DatabaseManager(self.config)
            await self.db.connect()
            logger.info("Database connected")
            
            # Initialize cache
            self.cache = CacheManager(self.config)
            await self.cache.connect()
            logger.info("Cache connected")
            
            # Initialize Steam API client
            self.steam_client = SteamAPIClient(
                api_key=self.config.get('steam.api_key')
            )
            logger.info("Steam API client initialized")
            
            # Initialize price tracker
            self.price_tracker = PriceTracker(self.db, self.cache)
            await self.price_tracker.start()
            logger.info("Price tracker started")
            
            # Load cogs
            await self.load_cogs()
            
            logger.info("Bot setup completed successfully")
            
        except Exception as e:
            logger.error(f"Error during bot setup: {e}")
            raise
    
    async def load_cogs(self):
        """
        Dynamically load all cog modules from the bot/cogs directory.
        """
        cogs_dir = Path('bot/cogs')
        
        if not cogs_dir.exists():
            logger.warning("Cogs directory not found")
            return
        
        for cog_file in cogs_dir.glob('*.py'):
            if cog_file.name.startswith('_'):
                continue
            
            cog_name = f"bot.cogs.{cog_file.stem}"
            try:
                await self.load_extension(cog_name)
                logger.info(f"Loaded cog: {cog_name}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog_name}: {e}")
    
    async def on_ready(self):
        """
        Event handler called when the bot is fully ready.
        """
        logger.info(f"Bot is ready! Logged in as {self.user}")
        logger.info(f"Bot ID: {self.user.id}")
        logger.info(f"Guilds: {len(self.guilds)}")
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="CS:GO Assets | !help"
            )
        )
    
    async def on_command_error(self, ctx, error):
        """
        Global error handler for commands.
        """
        await self.error_handler.handle(ctx, error)
    
    async def close(self):
        """
        Cleanup method called when the bot shuts down.
        """
        logger.info("Shutting down bot...")
        
        # Stop price tracker
        if self.price_tracker:
            await self.price_tracker.stop()
        
        # Close database connection
        if self.db:
            await self.db.close()
        
        # Close cache connection
        if self.cache:
            await self.cache.close()
        
        await super().close()
        logger.info("Bot shutdown complete")


def check_requirements():
    """
    Check if all required environment variables are set.
    """
    required_vars = [
        'DISCORD_TOKEN',
        'STEAM_API_KEY',
        'DATABASE_URL',
        'REDIS_URL'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)


async def main():
    """
    Main entry point for the bot.
    """
    # Check requirements
    check_requirements()
    
    # Create and run bot
    bot = CSGOAssetBot()
    
    try:
        async with bot:
            await bot.start(os.getenv('DISCORD_TOKEN'))
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        sys.exit(1)
