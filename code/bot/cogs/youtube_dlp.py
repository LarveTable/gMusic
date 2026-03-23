import yt_dlp
import discord
from discord import app_commands
import asyncio
import os
import json
from collections import deque
import glob

# Store active search tasks per user to allow cancellation if needed
active_search_tasks = {}

# Queue of cached songs to delete de oldest fast
cache = deque(maxlen=40) # Max 20 songs in cache

# Dictionary to store loaded info dicts
loaded_dicts = {}

def load_dicts_sync():
    global loaded_dicts # Modify the global loaded_dicts
    loaded = {}
    
    # Check if the temp_dicts directory exists, if not create it
    if not os.path.exists('code/bot/cogs/temp_dicts/'):
        os.makedirs('code/bot/cogs/temp_dicts/')

    # Load all .txt files in temp_dicts
    try:
        for filename in os.listdir('code/bot/cogs/temp_dicts/'):
            if filename.endswith('.txt'):
                try:
                    with open(f'code/bot/cogs/temp_dicts/{filename}', 'r') as f:
                        # Load json dict from file
                        info_dict = json.load(f)
                        # Load the dict in dict cache
                        loaded[info_dict['id']] = info_dict
                        # Add the id to the circular cache
                        cache.append(info_dict['id'])
                except Exception as e:
                    print(f'[YTDownload] --- Error loading dict from {filename}: {e}')
        loaded_dicts.update(loaded)
        print(f'[YTDownload] --- Loaded {len(loaded)} info dicts into memory.')
    except Exception as e:
        print(f'[YTDownload] --- Error loading dicts: {e}')
# Load the dicts synchronously at startup
load_dicts_sync()

# Youtube-DL options
ytdl_opts = {
    'format': 'wav/m4a/bestaudio', # Best audio format available with wav as priority
    'outtmpl': 'code/bot/cogs/temp_songs/%(id)s.%(ext)s', # Where to store downloaded files
    #'download_archive': 'code/bot/cogs/temp_songs/downloaded.txt', # Where to record downloaded files NOT USEFUL I THINK
    #'break_on_existing': True, TO TEST Skips the download if the file is present
    'no_warnings': True, # Suppress warnings, especially the sabr one
    'noplaylist': True, # Don't download playlists
    #'progress_hooks': [], # We will add hooks later, used to track download progress to inform the user
    #'sleep_interval': 2, # Sleep interval between downloads to avoid rate limiting TO TEST IF NEEDED
    #'sleep_interval_requests' : 1 # Sleep interval between extractions for security (especially if used with infinite AI playlist)
    'quiet': True, # Suppress output except for errors
}

# Youtube-DL options for fast extraction (no download)
ytdl_opts_fast_extractor = {
    'extract_flat': True, # Fast extraction, only metadata
    'skip_download': True, # Don't download the video/audio
    'noplaylist': True, # Don't download playlists
    'no_warnings': True, # Suppress warnings, especially the sabr one
    'extractor_args': { # Skip unnecessary extractors to speed up the process (but keep webpage and js to allow for the damn po token)
        'youtube': {
            'player_skip': ['configs', 'initial_data']
        }
    },
    'sleep_interval_requests' : 0.3, # Sleep interval between extractions for security
    'quiet': True, # Suppress output except for errors
    #'verbose': True # debug
}

ytdl = yt_dlp.YoutubeDL(ytdl_opts) # Load the basic downloader
ytdl_fast = yt_dlp.YoutubeDL(ytdl_opts_fast_extractor) # Load the fast extractor for search previews

# Check if the song is already downloaded from previous sessions
async def check_present(query : dict | str):
    # If the user pressed enter with a provided search result (speeds up the process) (if dict)
    if isinstance(query, dict):
        try:
            if query['id'] in loaded_dicts:
                    print(f'[YTDownload] --- Song \'{loaded_dicts[query['id']]['title']}\' found in memory.')
                    return loaded_dicts[query['id']]
            else:
                return query['url']
        except Exception as e:
            e.add_note('Error on query content in check_present.')
            raise e
    # If the query is an URL
    elif query.startswith('http://') or query.startswith('https://') or 'www.' in query:
        # Extract the infos
        result = await asyncio.to_thread(ytdl_fast.extract_info, query, download=False)
        # Check if the id is in loaded_dicts
        if result is not None:
            if result['id'] in loaded_dicts:
                print(f'[YTDownload] --- Song \'{result["title"]}\' found in memory.')
                return loaded_dicts[result['id']]
            else:
                return query
    # If the query is not an URL
    else :
        # Extract the infos
        result = await asyncio.to_thread(ytdl_fast.extract_info, f'ytsearch:{query}', download=False)
        # Check if the id is in loaded_dicts
        if result is not None and result['entries']:
            song = result['entries'][0]
            if song['id'] in loaded_dicts:
                print(f'[YTDownload] --- Song \'{song["title"]}\' found in memory.')
                return loaded_dicts[song['id']]
            # Get the url to speed up next download
            elif song['url']:
                return song['url']
    return None

# Removing songs and associated dicts
def remove_files(id):
    try:
        # Remove the dict
        os.remove(f'code/bot/cogs/temp_dicts/{id}.txt')
        # Remove the song file
        for file in glob.glob(f'code/bot/cogs/temp_songs/{id}.*'):
            os.remove(file)
        print(f'[YTDownload] --- Removed disk files for id: {id}')
    except Exception as e:
        print(f'[YTDownload] --- Error removing files for id \'{id}\': {e}')

# Cache handling function, id can't be already present as checked before calling this function
async def add_to_cache(id : str):
    global loaded_dicts # Modify the global loaded_dicts
    global cache # Modify the global cache
    
    # If cache is full
    if len(cache) == cache.maxlen:
        # Remove the oldest item
        old_id = cache.popleft()
        # Add the id to the cache
        cache.append(id)
        # Delete from memory
        if old_id in loaded_dicts:
            del loaded_dicts[old_id]
        print(f'[YTDownload] --- Cache full. Removed id \'{old_id}\' from memory and cache.')

        # Remove associated files (separate thread is not risky since the memory updates were made bafore this line)
        asyncio.create_task(asyncio.to_thread(remove_files, old_id))
    # If cache is not full
    else:
        # Add the new id to the cache
        cache.append(id)
    print(f'[YTDownload] --- Added id \'{id}\' to cache.')

# Prune data
def prune_data(data: dict):
    essential_fields = {
        'id': data.get('id'),
        'title': data.get('title'),
        'webpage_url': data.get('webpage_url'),
        'ext': data.get('ext'),
        'uploader': data.get('uploader'),
        'duration': data.get('duration'),
        'thumbnail': data.get('thumbnail'),
        'view_count': data.get('view_count'),
        'like_count': data.get('like_count'),
        'upload_date': data.get('upload_date'),
    }
    return essential_fields

# Asynchronously save the info dict to a text file
async def save_dict_async(info : dict):
    global loaded_dicts # Modify the global loaded_dicts
    # Save the essential fields as JSON
    with open(f'code/bot/cogs/temp_dicts/{info["id"]}.txt', 'w') as f:
        json.dump(info, f)
    # Add to circular cache
    await add_to_cache(info['id'])
    # Update the loaded_dicts in memory
    loaded_dicts[info['id']] = info
    print(f'[YTDownload] --- Added \'{info["title"]}\' to memory dicts.')
    print(f'[YTDownload] --- Saved dict on disk for \'{info["title"]}\' asynchronously.')

class YTDownload:

    @staticmethod
    # Blocking search function to be run in executor
    def _search_blocking(query):
        return ytdl_fast.extract_info(f'ytsearch5:{query}', download=False)
    
    @classmethod
    # Cancel the preview_results task for a specific user who ran the "/play youtube" command without waiting for previews
    def cancel_user_task(cls, user_id: int):
        if user_id in active_search_tasks:
            task = active_search_tasks[user_id]
            if not task.done():
                task.cancel()
                print(f"[YTDownload] --- Manually cancelled preview task for user **{user_id}** (Launched command).")
            # Now that the user is done typing, delete its entry in the active tasks dictionnary
            del active_search_tasks[user_id]

    # Preview the search results in discord
    @classmethod
    async def preview_results(cls, interaction : discord.Interaction, query : str): 
        # Get the user
        user_id = interaction.user.id
        
        # Cancel any existing task for this user
        if user_id in active_search_tasks:
            task = active_search_tasks[user_id]
            if not task.done():
                task.cancel()
        
        # If the query is an url or empty, return an empty choice list
        if query == "" or query.startswith('http://') or query.startswith('https://') or 'www.' in query:
            return []

        # Search runner with debounce
        async def search_runner():
            # Debounce delay
            await asyncio.sleep(0.3) 
            # If no input change, perform search
            return await asyncio.to_thread(cls._search_blocking, query)
        
        # Create and store the search task
        task = asyncio.create_task(search_runner())
        # Update the active task for this user
        active_search_tasks[user_id] = task

        # Return the previews as a list of choices (required by discord.py)
        try:
            # Wait for the search task to complete, but timeout after 2.5s if the previews were too slow to load
            results = await asyncio.wait_for(task, 2.5)

            # If not results, return empty list
            if results is None or not results['entries']:
                return []

            return [
                # Split the url to prevent exceeding the 'value' field limit
                app_commands.Choice(name=entry['title'], value=json.dumps({'url':entry['url'].split('https://www.youtube.com', 1)[1], 
                                                                           'id':entry['id']}, separators=(',', ':')))
                for entry in results['entries']
            ]
        # Do not return any choices if task was cancelled to avoid cache saving
        except asyncio.CancelledError:
            raise
        # If task took too long, return an empty list, screw the cache
        except asyncio.TimeoutError:
            []
        # If other exception occurs, log it and return empty list
        except Exception as e:
            print(f'[YTDownload] --- Error creating preview choices: {e}')
            print('[YTDownload] --- Skipping previews for this search.')
            return []
        # Finally, delete the active task entry in the dictionnary (memory management)
        finally:
            # Check if another task did not replace this one before deleting
            if active_search_tasks.get(user_id) == task:
                del active_search_tasks[user_id]
        
    # Search from user, either an URL or a query
    @classmethod
    async def search(cls, query : str):
        global cache # This function will modify the cache variable globally
        
        print(f'[YTDownload] --- Searching for \'{query if not isinstance(query, dict) else query['url']}\'...')
        # Check if the song is already present in temp_songs, if yes return it
        present = await check_present(query)
        if present is not None:
            # If cached result is a dict, return it directly
            if isinstance(present, dict):
                # Push to the head of the cache
                cache.remove(present['id'])
                cache.append(present['id'])
                print(f'[YTDownload] --- Moved id \'{present["id"]}\' to the head of the cache since already present.')
                print(f'[YTDownload] --- Using cached version of \'{present["title"]}\'.')
                return present
            # If not cached, use the found URL to speed up the process
            elif present.startswith('http://') or present.startswith('https://') or 'www.' in present:
                print(f'[YTDownload] --- \'{query if not isinstance(query, dict) else query['url']}\' not found in memory, downloading using found url.')
                # At this point, result shoud exist because of check_present
                try:
                    # Extract infos from url
                    result = await asyncio.to_thread(ytdl.extract_info, present, download=True)
                    result = prune_data(result) # Prune the result to only keep essential fields
                    # Save the info dict result in f'code/bot/cogs/temp_dicts/{result['id']}.txt' asynchronously, result from URL has no 'entries' field
                    asyncio.create_task(save_dict_async(result))
                    # Return the info dict result
                    print(f'[YTDownload] --- Downloaded \'{result["title"]}\' successfully.')
                    return result
                except Exception as e:
                    print(f'[YTDownload] --- Error when downloading or saving result for \'{query if not isinstance(query, dict) else query['url']}\': {e}')
                    raise e
        # Nothing was found
        print(f'[YTDownload] --- Nothing found for query: \'{query if not isinstance(query, dict) else query['url']}\'')
        return None
