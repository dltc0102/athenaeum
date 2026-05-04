import os, asyncio, httpx, pillow_avif
from PIL import ImageFile

from scripts.core.synopsis import Synopsis
from scripts.core.router import ComicRouter
from scripts.utils.archivist import Archivist
from scripts.utils.utils import create_async_client, color_msg, reset_dir, print_mem
from scripts.utils.progress import ComicProgress


async def scrape_main():
    ImageFile.LOAD_TRUNCATED_IMAGES = True

    current_config = os.path.join(os.getcwd(), "catalogue.json")
    merger_config_fp = os.path.join(os.getcwd(), "catalogue_db.json")

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0",
        "Accept": "image/*",
    }

    async_client: httpx.AsyncClient = create_async_client(headers)
    archivist_inst = Archivist(async_client)
    bot_task = asyncio.create_task(archivist_inst.run_bot())

    my_controls = None

    try:
        synopsis = Synopsis(current_config, merger_filepath=merger_config_fp)
        catalogue = synopsis.get_config_comics()
        catalogue_mtime = os.path.getmtime(current_config)

        print(color_msg("green", f"Found {len(catalogue)} comics to scrape."))

        temp_dir = os.path.join(os.getcwd(), "temp")
        await reset_dir(temp_dir)

        my_controls = ComicRouter(headers, async_client, archivist_inst)

        ComicProgress()
        print("comic progress cross-checked with catalogue")

        await my_controls.notify_message("> Starting to scrape!")

        print_mem("Bookshelf")
        print_mem("cover_images")
        print_mem("Aeronaeum")

        catalogue_index = 0

        while catalogue_index < len(catalogue):
            new_mtime = os.path.getmtime(current_config)

            if new_mtime != catalogue_mtime:
                print(color_msg("yellow", "[Scraper] catalogue.json changed. Reloading catalogue..."))

                synopsis = Synopsis(current_config, merger_filepath=merger_config_fp)
                catalogue = synopsis.get_config_comics()
                catalogue_mtime = os.path.getmtime(current_config)

                print(color_msg("green", f"[Scraper] Reloaded {len(catalogue)} comics."))

                catalogue_index = 0
                continue

            comic_config = catalogue[catalogue_index]

            try:
                comic_name = comic_config[0]
                domain_name = comic_config[1]

                comic_dirpath = os.path.join("Bookshelf", comic_name.replace("/", ""))

                if not os.path.exists(comic_dirpath):
                    print(color_msg("lightcyan", f"[MEM] {comic_name}: 0 B"))
                else:
                    print_mem(comic_name, comic_dirpath)

                if domain_name in ["mangafire", "ravenscans"]:
                    catalogue_index += 1
                    continue

                await my_controls.comic_redirect(comic_config)
                await asyncio.sleep(2)

            except Exception as e:
                print(color_msg("red", f"[SCRAPER ERROR] {comic_config[0]} failed: {e}"))

            catalogue_index += 1

    except asyncio.CancelledError:
        print(color_msg("red", "Scraper cancelled. Cleaning up..."))

    finally:
        if my_controls:
            progress_comics = my_controls.get_progress_comics()
            print(f"\nprogress comics: {len(progress_comics)}")

            failed_fetches = my_controls.get_failed_fetches()
            print(f"\nfailed fetches: {len(failed_fetches)}")
            for item in failed_fetches:
                print(item)

            configs_to_update = my_controls.configs_to_be_updated
            print(f"\nconfigs to be updated: {len(configs_to_update)}")
            for item in configs_to_update:
                print(item)

        print(color_msg("red", "Shutting down Discord bot..."))
        await archivist_inst.close_bot()

        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass

        await async_client.aclose()

        print(color_msg("green", "Scraper shutdown complete."))


if __name__ == "__main__":
    asyncio.run(scrape_main())