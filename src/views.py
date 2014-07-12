import tasks
import ast
import json
import pprint

from django.shortcuts import render, redirect
from django.template import RequestContext, loader, Context
from django.http import HttpResponseRedirect, HttpResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.urlresolvers import reverse

from audiosearch.settings import SEARCH_RESULT_DISPLAYED, ARTIST_SONGS_DISPLAYED, SIMILAR_ARTIST_DISPLAYED, REDIS_DEBUG, MORE_RESULTS, VIEW_DEBUG
from audiosearch.redis import client as RC
from src.calls import ArtistProfile, Playlist, SimilarArtists, ArtistSearch, SongSearch
from src.util import as_page


"""
---------------------------
Functions for serving pages
---------------------------
"""


def index(request):
    context = Context({})

    return render(request, 'index.html', context)


def search(request):
    """
    /search/
    """

    # obtain query params
    display_type = request.GET.get('type', "all").lower()
    search_name = request.GET.get('q')
    page = request.GET.get('page')

    # redirect on malformed request
    if search_name:
        search_name = search_name.lower()
    else:
        return HttpResponseRedirect('/')

    context = Context({
        'q': search_name,
        'type': display_type,
    })

    if REDIS_DEBUG:
        RC.delete(search_name)

    resource = RC.hgetall(search_name)

    # branch on @type, add paged results to context, call celery on missing resources
    if display_type == "artists":
        if 'artists' in resource:
            artists = ast.literal_eval(resource['artists'])
            context['paged_type'] = as_page(page, artists)
        else:
            tasks.call_service.delay(ArtistSearch(search_name))
            context['artists_pending'] = True

    elif display_type == "songs":
        if 'songs' in resource:
            songs = ast.literal_eval(resource['songs'])
            context['paged_type'] = as_page(page, songs)
        else:
            tasks.call_service.delay(SongSearch(search_name))
            context['songs_pending'] = True
    else:
        if 'artists' in resource:
            artists = ast.literal_eval(resource['artists'])
            context['paged_artists'] = as_page(page, artists)
        else:
            tasks.call_service.delay(ArtistSearch(search_name))
            context['artists_pending'] = True

        if 'songs' in resource:
            songs = ast.literal_eval(resource['songs'])
            context['paged_songs'] = as_page(page, songs)
        else:
            tasks.call_service.delay(SongSearch(search_name))
            context['songs_pending'] = True

    if VIEW_DEBUG:
        print
        print context
        print

    return render(request, 'search.html', context)


def artist_info(request):
    """
    /artist/
    """
    artist_id = request.GET['q']
    context = Context({
        'q': artist_id
    })

    if REDIS_DEBUG:
        RC.delete(artist_id)

    artist = RC.hgetall(artist_id)

    if 'profile' in artist:
        context['profile'] = ast.literal_eval(artist['profile'])
    else:
        tasks.call_service.delay(ArtistProfile(artist_id))

    if 'songs' in artist:
        context['songs'] = ast.literal_eval(artist['songs'])
        context['songs'] = context['songs'][:SEARCH_RESULT_DISPLAYED]
    else:
        tasks.call_service.delay(Playlist(artist_id))

    if 'similar' in artist:
        context['similar'] = ast.literal_eval(artist['similar'])
        context['similar'] = context['similar'][:SEARCH_RESULT_DISPLAYED]
    else:
        tasks.call_service.delay(SimilarArtists(artist_id))

    return render(request, 'artist.html', context)


def song_info (request):
    context = Context({})
    song_id = request.GET['q']

    return render(request, 'index.html', context)


# HTTP 500
def server_error(request):
    response = render(request, '500.html')
    response.status_code = 500
    return response


"""
-------------------------------------
Functions for handling ASYNC requests
-------------------------------------
"""

# check cache, if hit return json else return pending
def retrieve_resource(request):
    id_ = request.GET.get['q']
    resource = request.GET.get['resource']
    data = {}
    data_str = RC.hget(id_, resource)

    if data_str:
        data[resource] = ast.literal_eval(data_str)
        data['status'] = 'ready'
        data['page'] = request.GET.get['page']

    else:
        data['status'] = 'pending'

    return HttpResponse(json.dumps(data), content_type="application/json")


