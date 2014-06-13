from random import choice

__all__ = ['get_good_bio', 'remove_duplicates', 'get_similar_songs', 'map_artist_context', 'map_song_context']

# bios = list of artist biographies (dict)
# return wikipedia bio
#
# (todo ?): if wikibio does not exist, attempt to find a bio with: min < len (bio) < max 
def get_good_bio(bios):
    for b in bios:    
        if str(b['site']) == 'wikipedia':
            return b['text']

    return 'Artist biography is not available.'


# songs = incoming list of songs
# n = size of returned list
#
# remove duplicates (based on artist_id) and return list of size n
# if len (songs) < n, return list of size len (songs)
def remove_duplicates (songs, n):
    unique = []
    temp = {}

    for s in songs:
        t = s.title.lower(), s.artist_id

        if t not in temp:
            temp[t] = s
            unique.append(s)

        if len(unique) == n:
            break

    return unique


# artists = top 10 similar artists
# similar = list containing 10 randomly chosen songs
#
# create a list containing three songs from each similar artist
# note: this assumes best case of each artist having >= 3 songs
def get_similar_songs(artists):
    similar = []
    temp = {}
    count = 0

    for a in artists:

        # boundary check
        if len(a.songs) < 3:
            song_range = len(a.songs)
        else:
            song_range = 3

        # build dict
        for x in range(0, song_range):  
            temp[count] = a.songs[x]
            count += 1

    # randomly build return list
    for x in range(0, 10):
        key = random.choice (temp.keys())
        s = temp[key]

        similar.append(s)
        del temp[key]

    return similar


def map_artist_context (artist_, context):
    context = {}
    context['artist_id'] = artist_.id
    context['artist_name'] = artist_.name
    context['artist_terms'] = artist_.terms
    context['artist_rating'] = artist_.hotttnesss
    context['artist_twitter'] = artist_.get_twitter_id
    context['artist_similar'] = artist_.similar[:10]

    if artist_.images:
        image = choice(artist_.images)['url']
        context['artist_image'] = image

    if artist_.biographies:
        short = 300
        bio = get_good_bio(artist_.biographies).replace ('\n', '\n\n')

        context['artist_long_bio'] = bio
        context['artist_short_bio'] = bio[:short]

    # context['served'] = True

def map_song_context(songs, context):
    pass

    # notes
    # pyechonest.config.TRACE_API_CALLS = False, If true, API calls will be traced to the console
    # pyechonest.config.CALL_TIMEOUT = 10, The API call timeout (seconds)
    # 