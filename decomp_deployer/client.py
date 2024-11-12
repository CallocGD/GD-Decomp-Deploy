# -- Third party resources --
from aiohttp import ClientSession
from aiohttp_socks import ProxyConnector
from aiofiles import open as aopen

# Included with aiohttp
from yarl import URL

#  User-Agent bag
from .user_agents import random_useragent

from typing import Union
from pathlib import Path
import os
import asyncio


BINDINGS_URL = URL("https://raw.githubusercontent.com/geode-sdk/bindings/main/bindings")


def format_url(filename: str, ver: str):
    return BINDINGS_URL / ver / filename


def make_bindings_filenames(version: str):
    return {
        "GeometryDash.bro": format_url("GeometryDash.bro", version),
        "Extras.bro": format_url("Extras.bro", version),
        "Cocos2d.bro": format_url("Cocos2d.bro", version),
    }


class Client:
    """Used for downloading files and github repos clean and quickly..."""

    def __init__(self, proxy: str = "") -> None:
        # Make a temporary directory for the data unless otherwise...
        if not os.path.exists(".temp"):
            os.mkdir(".temp")

        self.client = ClientSession(
            connector=ProxyConnector.from_url(proxy) if proxy else None,
            headers={"User-Agent": random_useragent()},
            raise_for_status=True,
        )
        # Prevent ourselves from being rate-limited...
        self.limit = asyncio.Semaphore(2)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.close()

    async def downloadFile(self, FileUrl: str, name: Union[str, Path], temp:bool = True):
        async with aopen((Path(".temp") / name) if temp else name , "wb") as fp, self.limit:
            async with self.client.get(FileUrl) as resp:
                while r := await resp.content.read(1024):
                    await fp.write(r)

    async def downloadBindings(self, version: str):
        """Downloads and installs all the different broma stuff required for launching and compiling the broma files..."""
        for task in asyncio.as_completed(
            [
                asyncio.create_task(self.downloadFile(url, name))
                for name, url in make_bindings_filenames(version).items()
            ]
        ):
            await task


def destory_temp_dir():
    """Used as part of the cleanup operation..."""
    if os.path.exists(".temp"):
        os.remove(".temp")

