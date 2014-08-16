import ast
import json
import urllib

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.template import Context

import audiosearch.config as cfg
from src import services, utils, tasks
from audiosearch.redis import client as cache




def index(request, **kwargs):
    context = Context({})

    return render(request, 'index.html', context)




def search(request, **kwargs):
    normal_GET = utils.normalize(request.GET)
    normal_kwargs = utils.normalize(kwargs)

    q = normal_GET.get('q')

    if not q:
        return render(request, "search.html", Context({}))

    prefix = "search:"
    resource_name = urllib.unquote_plus(q)
    resource_id = prefix + resource_name
    page = normal_GET.get('page')
    page_type = normal_GET.get('type')

    context = Context({
        'resource_id': resource_id,
        'resource_name': resource_name,
        'page': page,
        'page_type': page_type,
        'data_is_paged': True if page_type else False,
        'use_generic_key': True if page_type else False,

        'debug': normal_kwargs.get('debug'),
    })

    service_map = {}

    if page_type == "artists":
        service_map['search_artists'] = services.SearchArtists(resource_name)
    
    elif page_type == "songs":
        service_map['search_songs'] = services.SearchSongs(resource_name)
    
    else:
        service_map['search_artists'] = services.SearchArtists(resource_name)
        service_map['search_songs'] = services.SearchSongs(resource_name)

    content = utils.generate_content(resource_id, service_map, page=page)
    
    if page_type == "artists" and 'search_artists' in content:
        content['content'] = content.pop('search_artists')

    elif page_type == "songs" and 'search_songs' in content:
        content['content'] = content.pop('search_songs')

    context.update(content)

    return render(request, "search.html", context)




def top_artists(request, **kwargs):
    prefix = "top:"
    resource_name = "artists"
    resource_id = prefix + resource_name
    content_key = 'top_artists'

    context = Context({
        'resource_id': resource_id,
        'data_is_paged': False,
        'use_generic_key': False,

        'debug': kwargs.get('debug'),
    })

    service_map = {
        'top_artists': services.TopArtists(),
    }

    content = utils.generate_content(resource_id, service_map)
    context.update(content)

    return render(request, 'top-artists.html', context)




def artist_home(request, **kwargs):
    normal_GET = utils.normalize(request.GET)
    normal_kwargs = utils.normalize(kwargs)
    resource_name = urllib.unquote_plus(normal_kwargs.get('artist'))
    
    if not resource_name:
        return redirect(top_artists)

    prefix = "artist:"
    resource_id = prefix + resource_name
    track_count = 15

    context = Context({
        'resource_id': resource_id,
        'resource_name': resource_name,
        'content_description': "popular tracks",
        'home_page': True,
        'data_is_paged': False,
        'use_generic_key': False,
        'item_count': track_count,

        'debug': kwargs.get('debug'),
    })

    service_map = {
        'profile': services.ArtistProfile(resource_name),
        'songs': services.ArtistSongs(resource_name),
    }

    content = utils.generate_content(resource_id, service_map, item_count=track_count)
    context.update(content)


    return render(request, "artist-home.html", context)




def artist_content(request, **kwargs):
    prefix = "artist:"
    resource_name = urllib.unquote_plus(kwargs['artist'])
    resource_id = prefix + resource_name
    content_key = urllib.unquote_plus(kwargs['content_key'])
    page = request.GET.get('page')

    context = Context({
        'resource_id': resource_id,
        'resource_name': resource_name,
        'page': page,
        'data_is_paged': True,
        'use_generic_key': True,
        'content_description': kwargs.get('description'),

        'debug': kwargs.get('debug'),
    })

    service_map = {}

    if content_key == "song_playlist":
        service_map[content_key] = services.Playlist(resource_name)
    
    elif content_key == "similar_artists": 
        service_map[content_key] = services.SimilarArtists(resource_name)
    
    elif content_key == "songs":
        service_map[content_key] = services.ArtistSongs(resource_name)

    content = utils.generate_content(resource_id, service_map, page=page)
    if content_key in content:
        content['content'] = content.pop(content_key)
    context.update(content)

    return render(request, "artist-content.html", context)




def song_home(request, **kwargs):
    prefix = "song:"
    artist = urllib.unquote_plus(kwargs['artist'])
    resource_name = urllib.unquote_plus(kwargs['song'])
    resource_id = prefix + artist + ":" + resource_name

    context = Context({
        'resource_id': resource_id,
        'resource_name': resource_name,
        'artist_name': artist,
        'home_page': True,
        'data_is_paged': False,
        'use_generic_key': False,

        'debug': kwargs.get('debug'),
    })

    service_map = {
        'profile': services.SongProfile(resource_name, artist),
    }

    content = utils.generate_content(resource_id, service_map)
    context.update(content)

    return render(request, "song-home.html", context)




def song_content(request, **kwargs):
    prefix = "song:"
    artist = urllib.unquote_plus(kwargs['artist'])
    resource_name = urllib.unquote_plus(kwargs['song'])
    resource_id = prefix + artist + ":" + resource_name
    content_key = urllib.unquote_plus(kwargs['content_key'])
    page = request.GET.get('page')

    context = Context({
        'resource_id': resource_id,
        'resource_name': resource_name,
        'artist_name': artist,
        'page': page,
        'data_is_paged': True,
        'use_generic_key': True,
        'content_description': kwargs.get('description'),

        'debug': kwargs.get('debug'),
    })

    service_map = {}

    if content_key == "song_playlist":
        service_map[content_key] = services.Playlist(resource_name, artist_id=artist)
    
    elif content_key == "similar_artists": 
        service_map[content_key] = services.SimilarArtists(artist)

    content = utils.generate_content(resource_id, service_map, page=page)
    if content_key in content:
        content['content'] = content.pop(content_key)
    context.update(content)

    return render(request, "song-content.html", context)




# HTTP 500
def server_error(request):
    response = render(request, "500.html")
    response.status_code = 500
    return response




"""
-------------------------------------
Functions for handling ASYNC requests
-------------------------------------
"""


def retrieve_content(request, **kwargs):
    resource_id = request.GET.get('resource_id').lower().strip()
    resource_id = utils.unescape_html(resource_id)
    content_key = request.GET.get('content_key')
    page = request.GET.get('page')
    item_count = request.GET.get('item_count')
    json_context = {}

    cache_data = cache.hget(resource_id, content_key)

    if cache_data:
        content = ast.literal_eval(cache_data)
        json_context['status'] = content.get('status')

        if json_context['status'] == "complete":
            json_context['data'] = utils.page_resource(page, content.get('data'), item_count)

    else:
        print "\nthis should never happen" * 3

    return HttpResponse(json.dumps(json_context), content_type="application/json")




def clear_resource(request):
    resource_id = utils.unescape_html(request.GET.get('resource_id'))

    try:
        resource_id = resource_id.lower()
        hit = cache.delete(resource_id)
    except AttributeError:
        hit = None

    pre = "REMOVED," if hit else "NOT FOUND,"
    banner = '\'' * len(pre)

    print
    print banner
    print "%s %s" %(pre, resource_id)
    print banner
    print

    return HttpResponse(json.dumps({}), content_type="application/json")



