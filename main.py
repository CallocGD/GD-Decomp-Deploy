from decomp_deployer import Client
import shutil
import asyncio 
import asyncclick as click
from writer import write_everything
import os


COCOS2D_REPO = "https://github.com/CallocGD/cocos-headers/archive/refs/heads/master.zip"


async def downloadBindings(proxy:str = "", version:str = "2.205"):
    async with Client(proxy) as client:
        print("[...] Installing Bindings...")
        await client.downloadBindings(version)
        print("[+] Bindings Installed")
    print("[...] Building Decomp Enviornment")
    write_everything()
    os.removedirs(".temp")
    print("[+] Decomp enviornment finished")

async def downloadCocos2d(proxy:str = ""):
    print("[...] Downloading Cocos2d and Other Geometry Dash External Libraries...")
    async with Client(proxy) as client:
        await client.downloadFile(COCOS2D_REPO, "cocos2d.zip", temp=False)
    shutil.unpack_archive("cocos2d.zip", "cocos2d")
    os.remove("cocos2d.zip")
    print("[+] Cocos2d Download Complete")


@click.command()
@click.option("--version", "-v", default="2.205")
@click.option("--proxy", "-p", default=None, help="Uses a proxy to download everything from")
async def cli(proxy:str, version:str):
    task1 = asyncio.create_task(downloadCocos2d(proxy))
    task2 = asyncio.create_task(downloadBindings(proxy, version))
    for t in asyncio.as_completed([task1, task2]):
        await t
    print("[+] Installation Completed")

if __name__ == "__main__":
    cli()