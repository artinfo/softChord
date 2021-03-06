# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#     * Rearrange models' order
#     * Make sure each model has one field with primary_key=True
# Feel free to rename the models, but don't rename db_table values or field names.
#
# Also note: You'll have to insert the output of 'django-admin.py sqlcustom [appname]'
# into your database.

from django.db import models


class SongChordLink(models.Model):
    id = models.IntegerField(null=True, primary_key=True, blank=True)
    song_id = models.IntegerField(null=True, blank=True)
    character_num = models.IntegerField(null=True, blank=True)
    note_id = models.IntegerField(null=True, blank=True)
    chord_type_id = models.IntegerField(null=True, blank=True)
    bass_note_id = models.IntegerField(null=True, blank=True)
    marker = models.TextField(blank=True)
    in_parentheses = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'song_chord_link'

class Songs(models.Model):
    id = models.IntegerField(null=True, primary_key=True, blank=True)
    text = models.CharField(max_length=1000, blank=True)
    title = models.TextField(blank=True)
    key_note_id = models.IntegerField(null=True, blank=True)
    key_is_major = models.NullBooleanField(null=True, blank=True)
    number = models.IntegerField(null=True, blank=True)
    class Meta:
        db_table = u'songs'

