import yt_dlp
import discord

ydl_opts = {
    'format': 'm4a/bestaudio/best',
    # ℹ️ See help(yt_dlp.postprocessor) for a list of available Postprocessors and their arguments
    'postprocessors': [{  # Extract audio using ffmpeg
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'm4a',
    }],
    'outtmpl': 'code/bot/cogs/temp_songs/%(title)s.%(ext)s',
    'noplaylist': True,
    'concurrent_fragment_downloads': 5,
    # 🔥 Utiliser aria2c comme téléchargeur
    'downloader': 'aria2c',
    'downloader_args': {
        'aria2c': [
            '-x', '16',   # jusqu'à 16 connexions par serveur
            '-s', '16',   # 16 téléchargements parallèles
            '-k', '1M'    # taille des morceaux
        ]
    }
}

class YTDownload(discord.PCMVolumeTransformer):

    # From a URL
    @classmethod
    async def from_url(cls, url, info_from_search=None, ydl=None):
       
        # Function to create a result dictionary
        def make_result(info, out):
            # Strip the file extension from the output path
            out = out.rsplit('.', 1)[0]
            # Add the file extension to the output path
            out += '.m4a' # This fixes a weird issue with yt-dlp giving a .mp4 extension instead of .m4a
            return {
                "path": out,
                "title": info.get("title"),
                "duration": info.get("duration"),
                "url": info.get("webpage_url"),
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader"),
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
                "upload_date": info.get("upload_date"),
            }

        # If ydl is not provided, create a new instance with the options
        if ydl is None:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    # This path means an url is provided, so we will download the video
                    info = ydl.extract_info(url, download=True) 
                    # Prepare the filename for the downloaded file
                    out = ydl.prepare_filename(info)
                    return make_result(info, out)
                except Exception as e:
                    print(f'Error downloading: {e}')
                    return None
        # If ydl is provided, use it to prepare the filename so we don't download the video again
        else:
            try:
                out = ydl.prepare_filename(info_from_search)
                return make_result(info_from_search, out)
            except Exception as e:
                print(f'Error preparing filename: {e}')
                return None
        
        
    # From a search query
    @classmethod
    async def from_search(cls, query):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Search for the query and get results
            info = ydl.extract_info(f'ytsearch:{query}', download=True)
            # If there are entries in the search results, call from_url with the first entry
            if info['entries']:
                return await cls.from_url(None, info_from_search=info['entries'][0], ydl=ydl)
            else:
                return None
        