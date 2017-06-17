# -*- coding: utf-8 -*-
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from gi.repository import Gtk
from quodlibet import _, app
from quodlibet.plugins import PluginConfigMixin
from quodlibet.plugins.songshelpers import has_bookmark
from quodlibet.plugins.events import EventPlugin
from quodlibet.qltk import Icons
from quodlibet.qltk.entry import UndoEntry
from quodlibet.qltk.tracker import TimeTracker


class SeekPointsPlugin(EventPlugin, PluginConfigMixin):
    """The plugin class."""

    PLUGIN_ID = "Seekpoints"
    PLUGIN_NAME = _("Seekpoint Bookmarks")
    PLUGIN_ICON = Icons.GO_JUMP
    PLUGIN_CONFIG_SECTION = __name__
    PLUGIN_DESC = _(
       "Store Seekpoints A and/or B for tracks. "
       "Skip to time A and stop after time B when track is played.\n"
       "Note that changing the names of the points below does not "
       "update the actual bookmark names, it only changes which "
       "bookmark names the plugin looks for when deciding whether to seek.")

    CFG_SEEKPOINT_A_TEXT = "A"
    CFG_SEEKPOINT_B_TEXT = "B"
    DEFAULT_A_TEXT = "A"
    DEFAULT_B_TEXT = "B"

    def enabled(self):
        self._seekpoint_A, self._seekpoint_B = self._get_seekpoints()
        self._try_create_tracker(force=True)

    def disabled(self):
        self._try_destroy_tracker()

    def _try_create_tracker(self, force=False):
        """Create the tracker if it does not exist,
           or if forced to, like at plugin enable"""
        if force or not self._tracker_is_enabled:
            self._tracker = TimeTracker(app.player)
            self._tracker.connect('tick', self._on_tick)
            self._tracker_is_enabled = True

    def _try_destroy_tracker(self):
        """Destroy the tracker if it exists"""
        if self._tracker_is_enabled:
            self._tracker.destroy()
            self._tracker_is_enabled = False

    def plugin_on_song_started(self, song):
        """Seeks to point A if it exists, and also tries to
           restart/recreate the tracker in case it was stopped/destroyed
           previously.
        """
        self._try_create_tracker()
        self._seekpoint_A, self._seekpoint_B = self._get_seekpoints()
        if not self._seekpoint_A:
            return
        self._seek(self._seekpoint_A)

    # Finishes track after point B has been reached, if it exists
    def _on_tick(self, tracker):
        """Temporarily stops/destroys the tracker in case there is no
           B-seekpoint, otherwise checks whether the current position
           is past that point each tick.
        """
        if not self._seekpoint_B:
            self._try_destroy_tracker()
            return

        time = app.player.get_position() // 1000
        if self._seekpoint_B <= time:
            self._seek(app.player.info("~#length"))

    def _get_seekpoints(self):
        """Reads seekpoint-names from config, which are compared to the
           bookmark-names of the current track to get timestamps (if any).
        """
        if not app.player.song:
            return None, None

        marks = []
        if has_bookmark(app.player.song):
            marks = app.player.song.bookmarks

        seekpoint_A = None
        seekpoint_B = None
        seekpoint_A_name = self.config_get(self.CFG_SEEKPOINT_A_TEXT,
                                           self.DEFAULT_A_TEXT)
        seekpoint_B_name = self.config_get(self.CFG_SEEKPOINT_B_TEXT,
                                           self.DEFAULT_B_TEXT)
        for time, mark in marks:
            if mark == seekpoint_A_name:
                seekpoint_A = time
            elif mark == seekpoint_B_name:
                seekpoint_B = time

        # if seekpoints are not properly ordered (or identical), the track
        # will likely endlessly seek when looping tracks, so discard B
        # (maybe raise an exception for the plugin list?).
        if (seekpoint_A is not None) and (seekpoint_B is not None):
            if seekpoint_A >= seekpoint_B:
                return seekpoint_A, None

        return seekpoint_A, seekpoint_B

    def _seek(self, seconds):
        app.player.seek(seconds * 1000)

    def PluginPreferences(self, parent):
        vb = Gtk.VBox(spacing=12)

        # Bookmark name to use for point A
        hb = Gtk.HBox(spacing=6)
        entry = UndoEntry()
        entry.set_text(self.config_get(self.CFG_SEEKPOINT_A_TEXT,
                                       self.DEFAULT_A_TEXT))
        entry.connect('changed', self.config_entry_changed,
                      self.CFG_SEEKPOINT_A_TEXT)
        lbl = Gtk.Label(label=_("Bookmark name for point A"))
        entry.set_tooltip_markup(_("Bookmark name to check for when "
            "a track is started, and if found the player seeks to that "
            "timestamp"))
        lbl.set_mnemonic_widget(entry)
        hb.pack_start(lbl, False, True, 0)
        hb.pack_start(entry, True, True, 0)
        vb.pack_start(hb, True, True, 0)

        # Bookmark name to use for point B
        hb = Gtk.HBox(spacing=6)
        entry = UndoEntry()
        entry.set_text(self.config_get(self.CFG_SEEKPOINT_B_TEXT,
                                       self.DEFAULT_B_TEXT))
        entry.connect('changed', self.config_entry_changed,
                      self.CFG_SEEKPOINT_B_TEXT)
        lbl = Gtk.Label(label=_("Bookmark name for point B"))
        entry.set_tooltip_markup(_("Bookmark name to use each tick during "
            "play of a track if it exist. If the current position exceeds "
            "the timestamp, seek to the end of the track."))
        lbl.set_mnemonic_widget(entry)
        hb.pack_start(lbl, False, True, 0)
        hb.pack_start(entry, True, True, 0)
        vb.pack_start(hb, True, True, 0)

        return vb