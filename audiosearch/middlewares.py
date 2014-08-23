from __future__ import absolute_import

import json
import urllib

from django.http import HttpResponse


class Normalizer(object):

    # Normalize kwargs and query parameters.  
    # Store normal query params in kwargs.
    def process_view(self, request, vfunc, vargs, vkwargs):

        # Kwargs.
        if len(vkwargs):
            for k, v in vkwargs.items():
                try:
                    vkwargs[k] = normalize(v)
                except AttributeError:
                    vkwargs[k] = v 

        # Query parameters.  Javascript strings (from ajax) must be unescaped (?).
        if len(request.GET):
            for param in request.GET:
                try:
                    # un_param = unescape_html(param) 
                    # vkwargs[param] = normalize(un_param)
                    vkwargs[param] = normalize(param)
                except AttributeError:
                    vkwargs[param] = param


# Convert item to lowercase, strip white space, and remove consecutive spaces.
def normalize(item):
    normal = item.strip().lower()
    normal = urllib.unquote_plus(normal)
    return ' '.join(normal.split())


# Remove escaping from ajax requests.
# TODO: see if I can remove this.
def unescape_html(s):
    s = s.replace("&lt;", "<")
    s = s.replace("&gt;", ">")
    s = s.replace("&amp;", "&")
    s = s.replace("&#39;", "'")

    return s
