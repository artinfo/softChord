# -*- coding: utf-8 -*-
"""

The main source file for softChord Editor

Writen by: Matvey Adzhigirey
Development started in December 2010

"""

# FIXME Use sqlite3 instead of QtSql, as this will allow this program to be
# more easily ported for use on the web. Moreover, sqlite3 provides a simpler,
# more Pythonic interface to SQLite than QtSql.


from PyQt4 import QtCore, QtGui, QtSql, uic
from PyQt4.QtCore import Qt
import sys, os

import sqlite3


db_file = "song_database.sqlite"


script_ui_file = "song_database_reader.ui"
chord_dialog_ui_file = "song_database_reader_chord_dialog.ui"

#if sys.executable.endswith("python.exe"):
    # Running in a Windows environment
#    script_ui_file = "song_database_reader.ui"
#else:
    # Running in Mac executaion environment
#    script_ui_file = os.path.join( os.path.dirname(sys.executable), "song_database_reader.ui" )


def tr(text):
    """
    Returns translated GUI text.
    """
    return text


class SongChord:
    """
    Class that stores specific chord information. This chord is for a
    specific letter in a specific song.
    """
    
    def __init__(self, app, id, song_id, character_num, note_id, chord_type_id, bass_note_id):
        self.app = app
        self.id = id
        self.song_id = song_id
        self.character_num = character_num
        self.note_id = note_id
        self.chord_type_id = chord_type_id
        self.bass_note_id = bass_note_id

    def transpose(self, steps):
        """
        Transpose this chord the specified number of steps up.
        <steps> can be negative.
        """
        self.note_id += steps
        if self.note_id < 0:
            self.note_id += 12
        elif self.note_id > 11:
            self.note_id -= 12
        
        if self.bass_note_id != -1:
            self.bass_note_id += steps
            if self.bass_note_id < 0:
                self.bass_note_id += 12
            elif self.bass_note_id > 11:
                self.bass_note_id -= 12

        
        query = QtSql.QSqlQuery()
        out = query.exec_("UPDATE song_chord_link SET note_id=%i, bass_note_id=%i WHERE id=%i" % (self.note_id, self.bass_note_id, self.id))
        
    
    def _getNoteString(self, note_id):
        """
        Returns the specified note as a string, using sharps vs flats
        as appropriate.
        """
        query = QtSql.QSqlQuery("SELECT text, alt_text FROM notes WHERE id=%i" % note_id)
        query.next()
        note_text = query.value(0).toString()
        note_alt_text = query.value(1).toString()
        
        if self.app.sharpsOrFlats() == 1:
            return note_text
        else:
            return note_alt_text
        
    def getChordString(self):
        """
        Returns string of the chord.
        For example, "Fm" or "Bbsus4"
        """
        note_text = self._getNoteString(self.note_id)
        
        query = QtSql.QSqlQuery("SELECT print FROM chord_types WHERE id=%i" % self.chord_type_id)
        query.next()
        chord_type_text = query.value(0).toString()
        
        chord_str = '%s%s' % (note_text, chord_type_text)
        
        if self.bass_note_id != -1:
            bass_note_text = self._getNoteString(self.bass_note_id)
            chord_str += "/%s" % bass_note_text
        
        return chord_str
    

class Song:
    """
    Stores information for a particular song.
    """
    def __init__(self, id, title, text, key_note_id, key_is_major, chords_dict):
        self.id = id
        self.title = title
        self.all_text = text
        self.key_note_id = key_note_id
        self.key_is_major = key_is_major
        self.all_chords = chords_dict
        
        # Break the song text into multiple lines:
        self._lines_list = [] # each item is a tuple of (text, chords)
        line_start_offset = 0
        line_end_offset = None
        remaining_text = self.all_text
        
        exit = False
        while not exit:
            char_num = unicode(remaining_text).find('\n')
            if char_num == -1:
                # This is the last line in the song
                exit = True
                line_text = remaining_text # text for this line
                line_end_offset = len(line_text) + line_start_offset
            else:
                # This is NOT the last line in the song
                line_text = remaining_text[:char_num] # text for this line
                remaining_text = remaining_text[char_num+1:]
                line_end_offset = char_num + line_start_offset
            
            self._lines_list.append(line_text)
            
            if char_num:
                # The start of the next line will be offset by char_num:
                line_start_offset += char_num+1
    

    def getNumLines(self):
        """
        Returns the number of lines in this song.
        """
        return len(self._lines_list)
    
    def getLineText(self, linenum):
        """
        Return the text for the specified line.
        """
        return self._lines_list[linenum]
    
    def iterateOverLines(self):
        """
        Iterate over each the lines in this song.
        """
        for line in self._lines_list:
            yield line

    def songCharToLineChar(self, song_char_num):
        """
        Given a character's global position in the song, return the
        character's line and line position.

        Returns a tuple of (linenum, char_num)
        """
        
        line_global_start = 0
        line_global_end = 0
        linenum = -1
        for line_text in self.iterateOverLines():
            linenum += 1
            line_global_end += len(line_text) + 1
            if song_char_num < line_global_end-1:
                # This character is in this line
                line_char_num = song_char_num - line_global_start
                return (linenum, line_char_num)
            line_global_start += len(line_text) + 1
        
        raise RuntimeError()


    def lineCharToSongChar(self, char_linenum, char_num):
        """
        Given the character position in the line, return its global
        position in the song.
        """
        
        out_char_num = 0
        linenum = -1
        for line_text in self.iterateOverLines():
            linenum += 1
            if linenum == char_linenum:
                return out_char_num + char_num
            else:
                out_char_num += len(line_text) + 1 # Add one for the end-of-line character
        raise RuntimeError()


class PrintWidget(QtGui.QWidget):
    """
    Widget for painting the current song.
    """
    def __init__(self, app):
        QtGui.QWidget.__init__(self, app.ui)
        self.app = app
        self.dragging_chord_orig_position = -1
        self.dragging_chord_curr_position = -1
        self.copying_chord = False # Whether the chord that is dragged will be copied instead of moved

        # So that hover mouse move events are generated:
        self.setMouseTracking(True)
    
    def paintEvent(self, ignored_event):
        """
        Called when the widget needs to draw the current song.
        """
        
        painter = QtGui.QPainter()
        painter.begin(self)
        
        # Draw into the whole widget:
        rect = self.rect()
        
        bgbrush = QtGui.QBrush(QtGui.QColor("white"))
        painter.fillRect(rect, bgbrush)
        
        self.app.drawSongToRect(painter, rect)
    
        painter.end()
    

    def leaveEvent(self, event):
        """
        Called when the mouse LEAVES the song chords widget.
        """
        
        # Clear the hovering highlighting:
        self.hover_char_num = None
        self.repaint()

    
    def mouseMoveEvent(self, event):
        """
        Called when mouse is DRAGGED or HOVERED in the song chords widget.
        """
        
        if self.geometry().contains(event.pos()):
            localx = event.pos().x()
            localy = event.pos().y()
            letter_tuple = self.app.determineClickedLetter(localx, localy)
            if letter_tuple:
                (is_chord, linenum, line_char_num, song_char_num) = letter_tuple
                # Mouse is over a vlid chord/letter
                
                if self.dragging_chord_curr_position == -1:
                    # Hovering, highlight the new chord/letter
                    self.app.hover_char_num = song_char_num

                else:
                    # Dragging
                    if self.dragging_chord_curr_position != -1:
                        # A chord is being dragged
                        
                        if song_char_num != self.dragging_chord_curr_position:
                            # The dragged chord was moved to a new position
                        
                            #key_modifiers = QtGui.QApplication.instance().keyboardModifiers() 
                            key_modifiers = event.modifiers() 
                            # shiftdown = key_modifiers & Qt.ShiftModifier
                            ctrl_down = bool(key_modifiers & Qt.ControlModifier)
                            #print 'ctrl_down:', ctrl_down

                            if self.copying_chord:
                                #print 'currently copying'
                                # The chord is currently drawn in both the original position and the curr_position
                                pass
                                """
                                if not ctrl_down:
                                    #print '  no longer copying, removing orig chord'
                                    # Just stopped copying, remove the orig chord.
                                    self.app.moveChord(self.dragging_chord_orig_position, -1)
                                    self.copying_chord = False
                                """
                            else:
                                #print 'currently not copying'
                                # The chord is currently drawn only in the the curr_position
                                if ctrl_down:
                                    #print '  will start copying, adding the original chord'
                                    # Copy the chord to the original position as well
                                    self.app.moveChord(self.dragging_chord_curr_position, self.dragging_chord_orig_position, copy=True)
                                    self.copying_chord = True
                                #print '  control is not pressed'

                            #print 'moving the dragged chord'
                            self.app.moveChord(self.dragging_chord_curr_position, song_char_num)
                            self.dragging_chord_curr_position = song_char_num
                            
                            # Show hover feedback on the new letter:
                            self.app.hover_char_num = song_char_num
                    else:
                        # No chord is being currently dragged. Clear previous selection:
                        self.app.selected_char_num = song_char_num
            
            self.app.print_widget.repaint()



    def mousePressEvent(self, event):
        """
        Called when mouse is CLICKED in the song chords widget.
        """

        if event.button() == Qt.LeftButton:
            localx = event.pos().x()
            localy = event.pos().y()
            letter_tuple = self.app.determineClickedLetter(localx, localy)
            if letter_tuple:
                # A valid letter/chord was clicked, select it:
                (is_chord, linenum, line_char_num, song_char_num) = letter_tuple
                
                if self.app.selected_char_num == song_char_num and is_chord:
                    # User clicked on the selected chord, initiate drag:
                    self.dragging_chord_curr_position = song_char_num
                    self.dragging_chord_orig_position = song_char_num
                    self.copying_chord = False
                else:
                    # User clicked on an un-selected chord. Select it:
                    self.app.selected_char_num = song_char_num
                    #self.dragging_chord_curr_position = -1
                    #self.dragging_chord_orig_position = -1
            else:
                self.app.selected_char_num = None
            self.app.print_widget.repaint()
    

    def mouseReleaseEvent(self, event):
        #if event.button() == Qt.LeftButton:

        # Stop dragging of the chord (it's already in the correct position):
        if self.dragging_chord_curr_position != -1:
            self.dragging_chord_curr_position = -1
            self.dragging_chord_orig_position = -1
        
        
    def mouseDoubleClickEvent(self, event):
        """
        Called when mouse is DOUBLE-CLICKED in the song chords widget.
        """
        
        if event.button() == Qt.LeftButton:
            localx = event.pos().x()
            localy = event.pos().y()
            letter_tuple = self.app.determineClickedLetter(localx, localy)
            if letter_tuple:
                # A valid chord/letter was double-clicked, edit it:
                self.app.selected_char_num = song_char_num
                (is_chord, linenum, line_char_num, song_char_num) = letter_tuple
                self.app.processSongCharEdit(song_char_num)
            else:
                # Invalid chord/letter was double clicked. Clear current selection:
                self.app.selected_char_num = None

            self.app.print_widget.repaint()

    


class ChordDialog:
    """
    Dialog for allowing the user to set the chord note & type.
    """

    def c(self, widget, signal_str, slot):
        self.ui.connect(widget, QtCore.SIGNAL(signal_str), slot)
    def __init__(self, app):
        self.app = app
        self.ui = uic.loadUi(chord_dialog_ui_file)
        
        notes_list = []
        query = QtSql.QSqlQuery("SELECT id, text, alt_text FROM notes")
        while query.next():
            note_id = query.value(0).toInt()[0]
            text = query.value(1).toString()
            alt_text = query.value(2).toString()
            if text == alt_text:
                combined_text = text
            else:
                combined_text = "%s/%s" % (text, alt_text)
            notes_list.append(combined_text)
        self.ui.note_menu.addItems(notes_list)


        chord_types_list = []
        query = QtSql.QSqlQuery("SELECT id, name FROM chord_types")
        while query.next():
            chord_type_id = query.value(0).toInt()[0]
            name = query.value(1).toString()
            chord_types_list.append(name)
        self.ui.chord_type_menu.addItems(chord_types_list)

        self.ui.bass_menu.addItems(["None"] + notes_list)

    def display(self, note_id=None, chord_type_id=None, bass_note_id=None):
        
        if note_id != None:
            self.ui.note_menu.setCurrentIndex(note_id)
        if chord_type_id != None:
            self.ui.chord_type_menu.setCurrentIndex(chord_type_id)
        if bass_note_id != None:
            # -1 becomes 0, etc:
            self.ui.bass_menu.setCurrentIndex(bass_note_id+1)
        
        self.ui.show()
        out = self.ui.exec_()
        if out: # OK pressed:
            note_id = self.ui.note_menu.currentIndex()
            chord_type_id = self.ui.chord_type_menu.currentIndex()
            # 0 (first item) will become -1 (invalid):
            bass_note_id = self.ui.bass_menu.currentIndex() - 1
            return (note_id, chord_type_id, bass_note_id)
        else:
            # Cancel pressed
            return None


class App:
    """
    The main application class.
    """
    def c(self, widget, signal_str, slot):
        self.ui.connect(widget, QtCore.SIGNAL(signal_str), slot)
    def __init__(self):
        self.ui = uic.loadUi(script_ui_file)
        
        # This qill be used for Qt (QSqlQuery) operations:
        self.db = QtSql.QSqlDatabase.addDatabase("QSQLITE")
        self.db.setDatabaseName(db_file)
        if not self.db.open():
            print 'Could not open the database'
            sys.exit(1)
        
        # This will be used for Python (sqlite3) operations:
        self.curs = sqlite3.connect(db_file)
        
        # FOR DEMONSTRATION:
        #for row in self.curs.execute("SELECT * FROM songs"):
        #    print row


        """
        self.notes_model = QtSql.QSqlQueryModel()
        self.notes_model.setQuery(QtSql.QSqlQuery("SELECT * from notes"))
        self.ui.notes_view.setModel(self.notes_model)
        self.ui.notes_view.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)

        self.chord_types_model = QtSql.QSqlQueryModel()
        self.chord_types_model.setQuery(QtSql.QSqlQuery("SELECT * from chord_types"))
        self.ui.chord_types_view.setModel(self.chord_types_model)
        self.ui.chord_types_view.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        
        #self.song_chord_link_model = QtSql.QSqlTableModel()
        self.song_chord_link_model = QtSql.QSqlRelationalTableModel()
        self.song_chord_link_model.setTable("song_chord_link")
        self.song_chord_link_model.setRelation(3, QtSql.QSqlRelation("notes", "id", "text"))
        self.song_chord_link_model.setRelation(4, QtSql.QSqlRelation("chord_types", "id", "name"))
        self.ui.song_chord_link_view.setItemDelegate(QtSql.QSqlRelationalDelegate(self.ui.song_chord_link_view))
        self.song_chord_link_model.setEditStrategy(QtSql.QSqlTableModel.OnFieldChange)
        self.song_chord_link_model.select()
        self.ui.song_chord_link_view.setModel(self.song_chord_link_model)
        self.ui.song_chord_link_view.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.c( self.song_chord_link_model, "dataChanged(QModelIndex, QModelIndex)",
            self.songChordLinkDataChanged )
        
        """
        
        self.createSongsModel()
        
        # Make a list of all keys:
        keys_list = []
        query = QtSql.QSqlQuery("SELECT id, text, alt_text FROM notes")
        while query.next():
            note_id = query.value(0).toInt()[0]
            text = query.value(1).toString()
            alt_text = query.value(2).toString()
            if text == alt_text:
                combined_text = text
            else:
                combined_text = "%s/%s" % (text, alt_text)
            keys_list.append(combined_text + " Major")
            keys_list.append(combined_text + " Minor")
        
        self.ui.song_key_menu.addItems(keys_list)
 
        
        self.ignore_song_text_changed = False
        self.previous_song_text = None # Song text before last user's edit operation
        self.c( self.ui.song_text_edit, "textChanged()", self.songTextChanged )
        
        self.c( self.ui.transpose_up_button, "clicked()", self.transposeUp )
        self.c( self.ui.transpose_down_button, "clicked()", self.transposeDown )
        self.c( self.ui.chord_font_button, "clicked()", self.changeChordFont )
        self.c( self.ui.text_font_button, "clicked()", self.changeLyricsFont )
        self.c( self.ui.export_pdf_button, "clicked()", self.exportToPdf )
        self.c( self.ui.new_song_button, "clicked()", self.createNewSong )
        self.c( self.ui.delete_song_button, "clicked()", self.deleteSelectedSong )
        
        self.c( self.ui.song_title_ef, "textEdited(QString)", self.currentSongTitleEdited )
        self.c( self.ui.song_key_menu, "currentIndexChanged(int)", self.currentSongKeyChanged )

        self.print_widget = PrintWidget(self)
        self.ui.chord_scroll_area.setWidgetResizable(False)
        self.ui.chord_scroll_area.setWidget(self.print_widget)
        
        self.current_song = None
        # The letter/chord that is currently selected:
        self.selected_char_num = None
        # The letter/chord that is currently hover (mouse hoveing over it):
        self.hover_char_num = None
        
        self.lyrics_font = QtGui.QFont("Times", 14)
        self.lyrics_font_metrics = QtGui.QFontMetrics(self.lyrics_font)
        self.chord_font = QtGui.QFont("Times", 10, QtGui.QFont.Bold)
        self.chord_font_metrics = QtGui.QFontMetrics(self.chord_font)
        self.ui.song_text_edit.setFont(self.lyrics_font)
        
        self._orig_keyPressEvent = self.ui.keyPressEvent
        self.ui.keyPressEvent = self.keyPressEvent

    def __del__(self):
        self.db.close()
    
    
    def createSongsModel(self):
        """
        Re-create the songs model to re-read it from the database.
        THERE MUST BE A BETTER WAY TO UPDATE THE MODEL?
        """
        
        if hasattr(self, "songs_model"):
            selected_row_indecies = self.ui.songs_view.selectionModel().selectedRows()
        else:
            selected_row_indecies = []
            
        """
        self.songs_model = QtSql.QSqlTableModel()
        self.songs_model.setTable("songs")
        self.songs_model.setEditStrategy(QtSql.QSqlTableModel.OnFieldChange)
        self.songs_model.select()
        self.songs_model.removeColumn(1) # Remove the text column
        self.songs_model.removeColumn(2) # Remove the chord note column
        self.songs_model.removeColumn(2) # Remove the is major column
        """
        self.songs_model = QtSql.QSqlQueryModel()
        self.songs_model.setQuery(QtSql.QSqlQuery("SELECT id, title from songs"))
        self.songs_model.setHeaderData(0, Qt.Horizontal, tr("ID"))
        self.songs_model.setHeaderData(1, Qt.Horizontal, tr("Title"))
        self.ui.songs_view.setModel(self.songs_model)
        self.ui.songs_view.horizontalHeader().setStretchLastSection(True)
        
        self.ui.songs_view.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        for index in selected_row_indecies:
            self.ui.songs_view.selectRow(index.row())

        self.c( self.ui.songs_view.selectionModel(), "selectionChanged(QItemSelection, QItemSelection)",
            self.songsSelectionChangedCallback )

    def keyPressEvent(self, event):
        """
        Will get called when a key is pressed
        """
        key = event.key()
        if key == Qt.Key_Delete or key == Qt.Key_Backspace:
            self.deleteSelectedChord()
        else:
            self._orig_keyPressEvent(event)
    

    def deleteSelectedChord(self):
        """
        Deletes the currently selected chord from the song.
        """
        
        if self.selected_char_num != None and self.current_song:
            song_char_num = self.selected_char_num
            
            song_id = self.current_song.id
            
            query = QtSql.QSqlQuery()
            out = query.exec_("DELETE FROM song_chord_link WHERE song_id=%i AND character_num=%i" % (song_id, song_char_num))
            
            self.selected_char_num = None
            self.updateCurrentSongFromDatabase()
            self.print_widget.repaint()

    def warning(self, text):
        QtGui.QMessageBox.warning(self.ui, "Warning", text)

    def info(self, text):
        QtGui.QMessageBox.information(self.ui, "Information", text)

    def setWaitCursor(self):
        self.ui.setCursor( QtGui.QCursor(QtCore.Qt.WaitCursor) )

    def restoreCursor(self):
        self.ui.setCursor( QtGui.QCursor(QtCore.Qt.ArrowCursor) )


    def songsSelectionChangedCallback(self, selected=None, deselected=None):
        """
        Called when the song selection changes.
        """
        self.selected_char_num = None # Remove the selection
        self.updateCurrentSongFromDatabase()
    

    def getSelectedSongIds(self):
        """
        Returns a list of selected songs (their song_ids)
        """

        selected_song_ids = []
        for index in self.ui.songs_view.selectionModel().selectedRows():
            song_id = self.songs_model.data(index).toInt()[0]
            selected_song_ids.append(song_id)
        return selected_song_ids
    

    def updateCurrentSongFromDatabase(self):
        """
        Re-reads the current song from the database.
        """
        
        selected_song_ids = self.getSelectedSongIds()
        
        if len(selected_song_ids) == 1:
            song_id = selected_song_ids[0]
            self.setCurrentSong(song_id)
            
            # Update the print_widget size:
            widget_width = self.ui.chord_scroll_area.width() - 20
            widget_height = self.ui.chord_scroll_area.height() - 2
            line_left = 20

            for linenum, line_text in enumerate(self.current_song.iterateOverLines()):
                chords_top, chords_bottom, lyrics_top, lyrics_bottom = self.getLineHeights(linenum)
                line_right = line_left + self.lyrics_font_metrics.width(line_text)
                if line_right > widget_width:
                    widget_width = line_right
                if lyrics_bottom > widget_height:
                    widget_height = lyrics_bottom
            
            self.print_widget.resize(widget_width, widget_height)
        else:
            self.current_song = None
        
        if self.current_song == None:
            self.ui.song_text_edit.setPlainText("")
            self.previous_song_text = None
            self.ui.song_title_ef.setText("")
            self.ui.song_key_menu.setCurrentIndex(0) # FIXME should be "None"
        
        self.ui.song_text_edit.setEnabled( self.current_song != None )
        self.ui.song_title_ef.setEnabled( self.current_song != None )
        self.ui.song_key_menu.setEnabled( self.current_song != None )
        self.ui.delete_song_button.setEnabled( len(selected_song_ids) > 0 )
        
        self.print_widget.repaint()
            
    
    def setCurrentSong(self, song_id):
        """
        Sets the current song to the specified song.
        Reads all song info from the database.
        """

        query = QtSql.QSqlQuery("SELECT title, text, key_note_id, key_is_major FROM songs WHERE id=%i" % song_id)
        query.next()
        song_title = query.value(0).toString()
        song_text = query.value(1).toString()
        song_key_note_id = query.value(2).toInt()[0]
        song_key_is_major = query.value(3).toInt()[0]
        
        if not self.ignore_song_text_changed:
            self.ignore_song_text_changed = True
            self.ui.song_text_edit.setPlainText(song_text)
            self.ignore_song_text_changed = False
            self.previous_song_text = song_text
        
        song_chords = {}
        query = QtSql.QSqlQuery("SELECT id, character_num, note_id, chord_type_id, bass_note_id FROM song_chord_link WHERE song_id=%i" % song_id)
        while query.next():
            id = query.value(0).toInt()[0]
            song_char_num = query.value(1).toInt()[0]
            note_id = query.value(2).toInt()[0]
            chord_type_id = query.value(3).toInt()[0]
            bass_note_id = query.value(4).toInt()[0]
            song_chords[song_char_num] = SongChord(self, id, song_id, song_char_num, note_id, chord_type_id, bass_note_id)
        
        chord_string = [' '] * len(song_text)
        for song_char_num, chord in song_chords.iteritems():
            try:
                chord_string[song_char_num] = chord
            except IndexError:
                pass
        
        self.current_song = Song(song_id, song_title, song_text, song_key_note_id, song_key_is_major, song_chords)

        self.ui.song_key_menu.setCurrentIndex( song_key_note_id*2 + song_key_is_major )
        self.ui.song_title_ef.setText(self.current_song.title)
        


    def sharpsOrFlats(self):
        """
        Returns 0 if "flat" versions of the chord should be printed,
        and returns 1 if "sharp" versions of the chords should be printed
        """
        if not self.current_song:
            return 1
        
        query = QtSql.QSqlQuery("SELECT note_id FROM song_chord_link WHERE song_id=%i" % self.current_song.id)
        num_prefer_sharp = 0
        num_prefer_flat = 0
        while query.next():
            note_id = query.value(0).toInt()[0]
            if note_id in [1, 6]: # C# or F#
                num_prefer_sharp += 1
            elif note_id in [3, 10]: # Eb or Bb
                num_prefer_flat += 1

        if num_prefer_flat > num_prefer_sharp:
            return 0 # flat
        else:
            return 1 # sharp


    #def songChordLinkDataChanged(self, topLeft, bottomRight):
    #    self.updateCurrentSongFromDatabase()

    def _transposeCurrentSong(self, steps):
        """
        Transpose the current song up by the specified number of steps.
        """
        
        for character_num, chord in self.current_song.all_chords.iteritems():
            chord.transpose(steps)
        self.updateCurrentSongFromDatabase()
    
    def songTextChanged(self):
        """
        Called when the song lyric text is modified by the user.
        """
        if self.ignore_song_text_changed:
            return
        if not self.current_song:
            return
        
        self.ignore_song_text_changed = True
        
        song_text = self.ui.song_text_edit.toPlainText()
        
        # Compare the new text to the previous text:
        
        if self.previous_song_text and self.previous_song_text != song_text:
            
            # For each character: key: old position, value: new position
            renumber_map = {}
            
            i = -1
            while True:
                i += 1
                try:
                    if song_text[i] != self.previous_song_text[i]:
                        break
                    else:
                        renumber_map[i] = i
                except IndexError:
                    # Reached end-of-line of either string
                    break
            num_preserved_begin_chars = i
            
            i = 0
            while True:
                i -= 1
                try:
                    if song_text[i] != self.previous_song_text[i]:
                        break
                    else:
                        renumber_map[ len(self.previous_song_text)+i ] = len(song_text)+i
                except IndexError:
                    # Reached end-of-line of either string
                    break
            num_preserved_end_chars = i
            


            # Renumber the chords:
            song_id = self.current_song.id
            query = QtSql.QSqlQuery("SELECT id, character_num FROM song_chord_link WHERE song_id=%i" % song_id)
            
            # NOTE SURE IF THESE ARE NEEDED: ??
            tmp_ids_to_delete = []
            tmp_id_song_char_num_dict = {}
            
            while query.next():
                id = query.value(0).toInt()[0]
                song_char_num = query.value(1).toInt()[0]
                try:
                    new_song_char_num = renumber_map[song_char_num]
                    tmp_id_song_char_num_list = []
                except KeyError:
                    tmp_ids_to_delete.append(id)
                    #query2 = QtSql.QSqlQuery()
                    #out = query2.exec_("DELETE FROM song_chord_link WHERE id=%i" % id)
                else:
                    tmp_id_song_char_num_dict[id] = new_song_char_num
                    #query2 = QtSql.QSqlQuery()
                    #out = query2.exec_("UPDATE song_chord_link SET character_num=%i WHERE id=%i" % (new_song_char_num, id))
            
            for id in tmp_ids_to_delete:    
                query2 = QtSql.QSqlQuery()
                out = query2.exec_("DELETE FROM song_chord_link WHERE id=%i" % id)

            for id, new_song_char_num in tmp_id_song_char_num_dict.iteritems():
                query2 = QtSql.QSqlQuery()
                out = query2.exec_("UPDATE song_chord_link SET character_num=%i WHERE id=%i" % (new_song_char_num, id))


            # Renumber the selection:
            if self.selected_char_num != None:
                self.selected_char_num = renumber_map.get(self.selected_char_num)
        
        self.previous_song_text = song_text
        
        song_id = self.current_song.id
        
        query = QtSql.QSqlQuery()
        out = query.exec_('UPDATE songs SET text="%s" WHERE id=%i' % (song_text, song_id))
        
        self.updateCurrentSongFromDatabase()
        
        self.ignore_song_text_changed = False
    

    def moveChord(self, song_char_num, new_song_char_num, copy=False):
        """
        Move the specified chord to a new position.
        If new_song_char_num == -1, then the chord is deleted.
        
        If copy is True, then copy the chord instead of moving it.
        """
        
        # Renumber the chords:
        song_id = self.current_song.id
        query = QtSql.QSqlQuery("SELECT id, note_id, chord_type_id, bass_note_id FROM song_chord_link WHERE song_id=%i AND character_num=%i" % (song_id, song_char_num))
        query.next()
        id = query.value(0).toInt()[0]
        
        if new_song_char_num == -1:
            # Delete
            query2 = QtSql.QSqlQuery()
            out = query2.exec_("DELETE FROM song_chord_link WHERE id=%i" % id)
        else:
            if copy:
                #print 'copying'
                # Copy
                note_id = query.value(1).toInt()[0]
                chord_type_id = query.value(2).toInt()[0]
                bass_note_id = query.value(3).toInt()[0]
                
                # Get the next available ID:
                query = QtSql.QSqlQuery("SELECT MAX(id) from song_chord_link")
                query.next()
                new_id = query.value(0).toInt()[0] + 1
                
                out = query.exec_("INSERT INTO song_chord_link (id, song_id, character_num, note_id, chord_type_id, bass_note_id) " + \
                            "VALUES (%i, %i, %i, %i, %i, %i)" % (new_id, song_id, new_song_char_num, note_id, chord_type_id, bass_note_id))
                #print 'copy out:', out
            else:
                #print 'moving'
                # Move
                query2 = QtSql.QSqlQuery()
                out = query2.exec_("UPDATE song_chord_link SET character_num=%i WHERE id=%i" % (new_song_char_num, id))
        self.updateCurrentSongFromDatabase()
    
    
    def transposeUp(self):
        self._transposeCurrentSong(1)

    def transposeDown(self):
        self._transposeCurrentSong(-1)
    
    def changeChordFont(self):
        """
        Brings up a dialog to let the user modify the chords font.
        """
        new_font, ok = QtGui.QFontDialog.getFont(self.chord_font, self.ui)
        if ok:
            self.chord_font = new_font
            self.chord_font_metrics = QtGui.QFontMetrics(self.chord_font)
            self.print_widget.repaint()

    def changeLyricsFont(self):
        """
        Brings up a dialog to let the user modify the lyrics font.
        """
        new_font, ok = QtGui.QFontDialog.getFont(self.lyrics_font, self.ui)
        if ok:
            self.lyrics_font = new_font
            self.lyrics_font_metrics = QtGui.QFontMetrics(self.lyrics_font)
            self.ui.song_text_edit.setFont(self.lyrics_font)
            self.print_widget.repaint()
    
    def exportToPdf(self):
        """
        Exports the selected songs to a PDF file.
        """
        # FIXME

        outfile = QtGui.QFileDialog.getSaveFileName(self.ui,
                    "Save PDF file as:",
                    ".", # initial dir
                    "PDF format (*.pdf)",
        )
        if outfile: 
            print 'outfile:', outfile
    

    def currentSongTitleEdited(self, new_title):
        """
        Called when the user modifies the selected song's title.
        """
        if self.current_song:
            query = QtSql.QSqlQuery()
            out = query.exec_('UPDATE songs SET title="%s" WHERE id=%i' % (new_title, self.current_song.id))
            
            # Update the song table from database:
            self.createSongsModel()
        

    def currentSongKeyChanged(self, new_key_index):
        """
        Called when the user modifies the selected song's key.
        """
        
        if self.current_song == None:
            return

        song_id = self.current_song.id

        note_id = new_key_index / 2
        is_major = new_key_index % 2
        
        if note_id != self.current_song.key_note_id and is_major != self.current_song.key_is_major:
            # Do not run this code if the value of the menu is first initialized
            query = QtSql.QSqlQuery()
            out = query.exec_('UPDATE songs SET key_note_id=%i, key_is_major=%i WHERE id=%i' % (note_id, is_major, song_id))
            
            # Update the song table from database:
            self.createSongsModel()
    
    
    def createNewSong(self):
        """
        Add a new song to the database and the songs table, and select it.
        """
        song_text = ""
        song_title = ""
        
        query = QtSql.QSqlQuery("SELECT MAX(id) from songs")
        query.next()
        id = query.value(0).toInt()[0] + 1

        out = query.exec_("INSERT INTO songs (id, text, title) " + \
                        'VALUES (%i, "%s", "%s")' % (id, song_text, song_title))
        
        # Update the song table from database:
        self.createSongsModel()
        
        # Select the newly added song:
        self.ui.songs_view.selectRow( self.songs_model.rowCount()-1 )
        self.updateCurrentSongFromDatabase()
    
    def deleteSelectedSong(self):
        selected_song_ids = self.getSelectedSongIds()
        for song_id in selected_song_ids:
            query = QtSql.QSqlQuery()
            out = query.exec_("DELETE FROM songs WHERE id=%i" % song_id)
            
            # Delete all associated chords:   
            query = QtSql.QSqlQuery()
            out = query.exec_("DELETE FROM song_chord_link WHERE song_id=%i" % song_id)
        
        # Update the song table from database:
        self.createSongsModel()
    
    
    def drawSongToRect(self, painter, rect):
        """
        Draws the current song text to the specified rect.
        """
        
        if not self.current_song:
            return
        
        selection_brush = QtGui.QPalette().highlight()
        hover_brush = QtGui.QColor("light grey")
        
        line_left = 20

        for linenum, line_text in enumerate(self.current_song.iterateOverLines()):
            
            chords_top, chords_bottom, lyrics_top, lyrics_bottom = self.getLineHeights(linenum)
            
            
            if self.hover_char_num != None:
                # Mouse is currently hovering over this letter:
                hover_linenum, hover_line_char_num = self.current_song.songCharToLineChar(self.hover_char_num)
                if hover_linenum == linenum:
                    letter_left = line_left + self.lyrics_font_metrics.width( line_text[:hover_line_char_num] )
                    letter_right = line_left + self.lyrics_font_metrics.width( line_text[:hover_line_char_num+1] )
                    
                    # Draw a selection rectangle:
                    painter.fillRect(letter_left, lyrics_top, letter_right-letter_left, lyrics_bottom-lyrics_top, hover_brush)
            
            if self.selected_char_num != None:
                selected_linenum, selected_line_char_num = self.current_song.songCharToLineChar(self.selected_char_num)
                if selected_linenum == linenum:
                    letter_left = line_left + self.lyrics_font_metrics.width( line_text[:selected_line_char_num] )
                    letter_right = line_left + self.lyrics_font_metrics.width( line_text[:selected_line_char_num+1] )
            
                    # Draw a selection rectangle:
                    painter.fillRect(letter_left, lyrics_top, letter_right-letter_left, lyrics_bottom-lyrics_top, selection_brush)

            
            painter.setFont(self.lyrics_font)
            line_right = line_left + self.lyrics_font_metrics.width(line_text)
            painter.drawText(line_left, lyrics_top, line_right-line_left, lyrics_bottom-lyrics_top, QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, line_text)

            painter.setFont(self.chord_font)

            #print 'hover_char_num:', self.hover_char_num
            #print 'selected_char_num:', self.selected_char_num

            for song_char_num, chord in self.current_song.all_chords.iteritems():
                chord_linenum, line_char_num = self.current_song.songCharToLineChar(song_char_num)
                if chord_linenum != linenum:
                    continue

                letter_left = line_left + self.lyrics_font_metrics.width( line_text[:line_char_num] )
                letter_right = line_left + self.lyrics_font_metrics.width( line_text[:line_char_num+1] )
                chord_middle = (letter_left + letter_right) / 2 # Average of left and right
                
                chord_text = chord.getChordString()
                chord_width = self.chord_font_metrics.width(chord_text)
                chord_left = chord_middle - (chord_width/2)
                chord_right = chord_middle + (chord_width/2)
                
                if song_char_num == self.hover_char_num:
                    # Draw a hover rectangle:
                    painter.fillRect(chord_left, chords_top, chord_right-chord_left, chords_bottom-chords_top, hover_brush)
                
                if song_char_num == self.selected_char_num:
                    # Draw a selection rectangle:
                    painter.fillRect(chord_left, chords_top, chord_right-chord_left, chords_bottom-chords_top, selection_brush)
                
                painter.drawText(chord_left, chords_top, chord_right-chord_left, chords_bottom-chords_top, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignBottom, chord_text)
            
            

    
    def determineClickedLetter(self, x, y):
        """
        Determine where the specified (local) mouse coordinates position.
        That is, which lyric or chord letter was the mouse above when this
        event happened.
        """
        
        if not self.current_song:
            return None

        line_left = 20
        
        for linenum in range(self.current_song.getNumLines()):
            line_text = self.current_song.getLineText(linenum)
            
            chords_top, chords_bottom, lyrics_top, lyrics_bottom = self.getLineHeights(linenum)
            
            if y < chords_top or y > lyrics_bottom:
                continue # Not this line
            
            #print 'mouse event on line:', linenum
            
            # Figure out the lyric letter for the mouse location:
            song_char_num = -1
            for line_char_num in range(len(line_text)):
                left = line_left + self.lyrics_font_metrics.width( line_text[:line_char_num] )
                right = line_left + self.lyrics_font_metrics.width( line_text[:line_char_num+1] )
                if x > left and x < right:
                    song_char_num = self.current_song.lineCharToSongChar(linenum, line_char_num)
                    break
            
            #print 'song_char_num:', song_char_num
            
            if y < chords_bottom:
                is_chord = True
                
                # Figure out if a chord is attached to this letter:
                for chord_song_char_num, chord in self.current_song.all_chords.iteritems():
                    chord_linenum, line_char_num = self.current_song.songCharToLineChar(chord_song_char_num)
                    if chord_linenum != linenum:
                        continue

                    # Figure out the y position where the should be drawn:
                    letter_left = line_left + self.lyrics_font_metrics.width( line_text[:line_char_num] )
                    letter_right = line_left + self.lyrics_font_metrics.width( line_text[:line_char_num+1] )

                    chord_middle = (letter_left + letter_right) / 2 # Average of left and right
                    
                    chord_text = chord.getChordString()
                    chord_width = self.chord_font_metrics.width(chord_text)
                    chord_left = chord_middle - (chord_width/2)
                    chord_right = chord_middle + (chord_width/2)
                    
                    if x > chord_left and x < chord_right:
                        chord_song_char_num = self.current_song.lineCharToSongChar(linenum, line_char_num)
                        # Location is on an existing chord
                        return (is_chord, linenum, line_char_num, chord_song_char_num)
                
                # Location is NOT on an existing chord
                if song_char_num == -1:
                    #print 'exit1'
                    return None

                #print 'event in a chord'
                return (is_chord, None, None, song_char_num)
            
            
            elif y > lyrics_top:
                # Location is above a lyric letter
                is_chord = False
                if song_char_num == -1:
                    #print 'exit2'
                    return None
                
                #print 'event in a letter'
                return (is_chord, None, None, song_char_num)
                #for line_char_num in range(len(line_text)):
                #    left = line_left + self.lyrics_font_metrics.width( line_text[:line_char_num] )
                #    right = line_left + self.lyrics_font_metrics.width( line_text[:line_char_num+1] )
                #    if x > left and x < right:
                #        song_char_num = self.current_song.lineCharToSongChar(linenum, line_char_num)
                #        return (is_chord, linenum, line_char_num, song_char_num)
        
        #print 'exit3'
        return None

        
    
    def processSongCharEdit(self, song_char_num):
        """
        Bring up a dialog that will allow the user to add/modify the chord at
        the specified position.
        """
        
        # Check whether this character already has a chord:
        song_id = self.current_song.id
        query = QtSql.QSqlQuery("SELECT id, character_num, note_id, chord_type_id, bass_note_id FROM song_chord_link WHERE song_id=%i AND character_num=%i" % (song_id, song_char_num))
        if query.next():
            id = query.value(0).toInt()[0]
            note_id = query.value(2).toInt()[0]
            chord_type_id = query.value(3).toInt()[0]
            bass_note_id = query.value(4).toInt()[0]
            chord_tuple = ChordDialog(self).display(note_id, chord_type_id, bass_note_id)
        else:
            chord_tuple = ChordDialog(self).display()
        
        if chord_tuple:
            # Ok pressed
            (note_id, chord_type_id, bass_note_id) = chord_tuple
            
            # Check whether this character already has a chord, if so, alter it:
            query = QtSql.QSqlQuery("SELECT id FROM song_chord_link WHERE song_id=%i AND character_num=%i" % (song_id, song_char_num))
            if query.next():
                # Replacing exising chord
                id = query.value(0).toInt()[0]
                query = QtSql.QSqlQuery()
                out = query.exec_("UPDATE song_chord_link SET note_id=%i, chord_type_id=%i, bass_note_id=%i WHERE id=%i" % (note_id, chord_type_id, bass_note_id, id))
            else:
                # Adding a new chord
                query = QtSql.QSqlQuery("SELECT MAX(id) from song_chord_link")
                query.next()
                id = query.value(0).toInt()[0] + 1
                
                query = QtSql.QSqlQuery()
                out = query.exec_("INSERT INTO song_chord_link (id, song_id, character_num, note_id, chord_type_id, bass_note_id) " + \
                            "VALUES (%i, %i, %i, %i, %i, %i)" % (id, song_id, song_char_num, note_id, chord_type_id, bass_note_id))
            self.updateCurrentSongFromDatabase()
                

    
    def getLineHeights(self, linenum):
        """
        Returns top & bottom y positions of the chords and lyrics texts
        for the specified line.
        """
        lyrics_height = self.lyrics_font_metrics.height()
        
        chords_height = self.chord_font_metrics.height()
        
        line_height = lyrics_height + chords_height
        line_height *= 0.9 # So that there is less spacing between the chords and the text
        
        line_top = linenum * line_height

        chords_top = line_top
        chords_bottom = chords_top + chords_height
        lyrics_bottom = line_top + line_height
        lyrics_top = lyrics_bottom - lyrics_height

        
        return chords_top, chords_bottom, lyrics_top, lyrics_bottom
    
    


# Main event loop:

qapp = QtGui.QApplication(sys.argv)
window = App()
window.ui.show()
sys.exit(qapp.exec_())


#EOF