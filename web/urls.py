from django.conf.urls.defaults import patterns, include, url

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'softchord_web.views.home', name='home'),
    # url(r'^softchord_web/', include('softchord_web.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    #url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    #url(r'^admin/', include(admin.site.urls)),

    (r'^songs/(?P<song_id>[^/]+)/$', 'web.softchord.views.view_song'),
    (r'^songs/$', 'web.softchord.views.view_all'),
    #(r'^songs/(?P<song_id>[^/]+)/edit/$', 'web.softchord.views.edit_song'),


)
