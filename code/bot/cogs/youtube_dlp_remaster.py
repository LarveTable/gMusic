import yt_dlp
import discord
from discord import app_commands

ytdl_opts = {
    'format': 'wav/m4a/bestaudio', # Best audio format available with wav as priority
    'outtmpl': 'code/bot/cogs/temp_songs/%(id)s.%(ext)s', # Where to store downloaded files
    #'download_archive': 'code/bot/cogs/temp_songs/downloaded.txt', # Where to record downloaded files NOT USEFUL I THINK
    #'break_on_existing': True, TO TEST Skips the download if the file is present
    'noplaylist': True, # Don't download playlists
    #'quiet': True, Don't output the logs in console
    'progress_hooks': [], # We will add hooks later, used to track download progress to inform the user
    'sleep_interval': 2, # Sleep interval between downloads to avoid rate limiting TO TEST IF NEEDED
    'sleep_interval_requests' : 1 # Sleep interval between extractions for security (especially if used with infinite AI playlist)
}

ytdl_opts_fast_extractor = {
    'extract_flat': True, # Fast extraction, only metadata
    'skip_download': True, # Don't download the video/audio
    'player_skip': ['configs', 'webpage', 'js', 'initial_data'], # Skip unnecessary extractors to speed up the process
    'sleep_interval_requests' : 0.3 # Sleep interval between extractions for security
}

ytdl = yt_dlp.YoutubeDL(ytdl_opts) # Load the basic downloader
ytdl_fast = yt_dlp.YoutubeDL(ytdl_opts_fast_extractor) # Load the fast extractor for search previews

class YTDownload(discord.PCMVolumeTransformer):
    # Preview the search results in discord
    @classmethod
    async def preview_results(cls, interaction : discord.Interaction, query : str):
        # If the query is an url or empty, return an empty choice list
        if query == "" or query.startswith('http://') or query.startswith('https://'):
            return []
        # If the query is not an URL or empty
        results = ytdl_fast.extract_info(f'ytsearch5:{query}', download=False)
        # If nothing is found (is it possible ?)
        if results is None or not results['entries']:
            return []
        # Return the previews as a list of choices (required by discord.py)
        return [
            app_commands.Choice(name=entry['title'], value=entry['url'])
            for entry in results['entries']
        ]
        
    # Search from user, either an URL or a query
    @classmethod
    async def search(cls, query):
        # Extract infos from url query
        if query.startswith('http://') or query.startswith('https://'):
            result = ytdl.extract_info(query, download=True)
        # Extract infos from text query
        else:
            result = ytdl.extract_info(f'ytsearch:{query}', download=True)
        # If something is found
        if result is not None and result['entries']:
            return result['entries'][0]
        # Nothing was found
        return None
