# -*- coding: utf-8 -*-
#!/usr/bin/env python
#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2000-2007  Donald N. Allingham
# Copyright (C) 2007       Johan Gonqvist <johan.gronqvist@gmail.com>
# Copyright (C) 2007-2009  Gary Burton <gary.burton@zen.co.uk>
# Copyright (C) 2007-2009  Stephane Charette <stephanecharette@gmail.com>
# Copyright (C) 2008-2009  Brian G. Matherly
# Copyright (C) 2008       Jason M. Simanek <jason@bohemianalps.com>
# Copyright (C) 2008-2011  Rob G. Healey <robhealey1@gmail.com>
# Copyright (C) 2010       Doug Blank <doug.blank@gmail.com>
# Copyright (C) 2010       Jakim Friant
# Copyright (C) 2010-2017  Serge Noiraud
# Copyright (C) 2011       Tim G L Lyons
# Copyright (C) 2013       Benny Malengier
# Copyright (C) 2016       Allen Crider
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

"""
Narrative Web Page generator.

Classe:
    EventPage - Event index page and individual Event pages
"""
#------------------------------------------------
# python modules
#------------------------------------------------
from collections import defaultdict
from operator import itemgetter
from decimal import getcontext
import logging

#------------------------------------------------
# Gramps module
#------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.lib import (Date, Event)
from gramps.gen.plug.report import Bibliography
from gramps.plugins.lib.libhtml import Html

#------------------------------------------------
# specific narrative web import
#------------------------------------------------
from gramps.plugins.webreport.basepage import BasePage
from gramps.plugins.webreport.common import (get_first_letters, _ALPHAEVENT,
                                             _EVENTMAP, alphabet_navigation,
                                             FULLCLEAR, sort_event_types,
                                             primary_difference,
                                             get_index_letter)

_ = glocale.translation.sgettext
LOG = logging.getLogger(".NarrativeWeb")
getcontext().prec = 8

#################################################
#
#    creates the Event List Page and EventPages
#
#################################################
class EventPages(BasePage):
    """
    This class is responsible for displaying information about the 'Person'
    database objects. It displays this information under the 'Events'
    tab. It is told by the 'add_instances' call which 'Person's to display,
    and remembers the list of persons. A single call to 'display_pages'
    displays both the Event List (Index) page and all the Event
    pages.

    The base class 'BasePage' is initialised once for each page that is
    displayed.
    """
    def __init__(self, report):
        """
        @param: report -- The instance of the main report class for
                          this report
        """
        BasePage.__init__(self, report, title="")
        self.event_handle_list = []
        self.event_types = []
        self.event_dict = defaultdict(set)

    def display_pages(self, title):
        """
        Generate and output the pages under the Event tab, namely the event
        index and the individual event pages.

        @param: title -- Is the title of the web page
        """
        LOG.debug("obj_dict[Event]")
        for item in self.report.obj_dict[Event].items():
            LOG.debug("    %s", str(item))
        event_handle_list = self.report.obj_dict[Event].keys()
        event_types = []
        for event_handle in event_handle_list:
            event = self.r_db.get_event_from_handle(event_handle)
            event_types.append(self._(event.get_type().xml_str()))
        message = _("Creating event pages")
        with self.r_user.progress(_("Narrated Web Site Report"), message,
                                  len(event_handle_list) + 1
                                 ) as step:
            index = 1
            for event_handle in event_handle_list:
                step()
                index += 1
                self.eventpage(self.report, title, event_handle)
            step()
        self.eventlistpage(self.report, title, event_types,
                           event_handle_list)

    def eventlistpage(self, report, title, event_types, event_handle_list):
        """
        Will create the event list page

        @param: report            -- The instance of the main report class for
                                     this report
        @param: title             -- Is the title of the web page
        @param: event_types       -- A list of the type in the events database
        @param: event_handle_list -- A list of event handles
        """
        BasePage.__init__(self, report, title)
        ldatec = 0
        prev_letter = " "

        output_file, sio = self.report.create_file("events")
        eventslistpage, head, body = self.write_header(self._("Events"))

        # begin events list  division
        with Html("div", class_="content", id="EventList") as eventlist:
            body += eventlist

            msg = self._("This page contains an index of all the events in the "
                         "database, sorted by their type and date (if one is "
                         "present). Clicking on an event&#8217;s Gramps ID "
                         "will open a page for that event.")
            eventlist += Html("p", msg, id="description")

            # get alphabet navigation...
            index_list = get_first_letters(self.r_db, event_types,
                                           _ALPHAEVENT)
            alpha_nav = alphabet_navigation(index_list, self.rlocale)
            if alpha_nav:
                eventlist += alpha_nav

            # begin alphabet event table
            with Html("table",
                      class_="infolist primobjlist alphaevent") as table:
                eventlist += table

                thead = Html("thead")
                table += thead

                trow = Html("tr")
                thead += trow

                trow.extend(
                    Html("th", label, class_=colclass, inline=True)
                    for (label, colclass) in [(self._("Letter"),
                                               "ColumnRowLabel"),
                                              (self._("Type"), "ColumnType"),
                                              (self._("Date"), "ColumnDate"),
                                              (self._("Gramps ID"),
                                               "ColumnGRAMPSID"),
                                              (self._("Person"), "ColumnPerson")
                                             ]
                )

                tbody = Html("tbody")
                table += tbody

                # separate events by their type and then thier event handles
                for (evt_type,
                     data_list) in sort_event_types(self.r_db,
                                                    event_types,
                                                    event_handle_list,
                                                    self.rlocale):
                    first = True
                    _event_displayed = []

                    # sort datalist by date of event and by event handle...
                    data_list = sorted(data_list, key=itemgetter(0, 1))
                    first_event = True

                    for (sort_value, event_handle) in data_list:
                        event = self.r_db.get_event_from_handle(event_handle)
                        _type = event.get_type()
                        gid = event.get_gramps_id()
                        if event.get_change_time() > ldatec:
                            ldatec = event.get_change_time()

                        # check to see if we have listed this gramps_id yet?
                        if gid not in _event_displayed:

                            # family event
                            if int(_type) in _EVENTMAP:
                                handle_list = set(
                                    self.r_db.find_backlink_handles(
                                        event_handle,
                                        include_classes=['Family', 'Person']))
                            else:
                                handle_list = set(
                                    self.r_db.find_backlink_handles(
                                        event_handle,
                                        include_classes=['Person']))
                            if handle_list:

                                trow = Html("tr")
                                tbody += trow

                                # set up hyperlinked letter for
                                # alphabet_navigation
                                tcell = Html("td", class_="ColumnLetter",
                                             inline=True)
                                trow += tcell

                                if evt_type and not evt_type.isspace():
                                    letter = get_index_letter(
                                        self._(str(evt_type)[0].capitalize()),
                                        index_list, self.rlocale)
                                else:
                                    letter = "&nbsp;"

                                if first or primary_difference(letter,
                                                               prev_letter,
                                                               self.rlocale):
                                    first = False
                                    prev_letter = letter
                                    t_a = 'class = "BeginLetter BeginType"'
                                    trow.attr = t_a
                                    ttle = self._("Event types beginning "
                                                  "with letter %s") % letter
                                    tcell += Html("a", letter, name=letter,
                                                  id_=letter, title=ttle,
                                                  inline=True)
                                else:
                                    tcell += "&nbsp;"

                                # display Event type if first in the list
                                tcell = Html("td", class_="ColumnType",
                                             title=self._(evt_type),
                                             inline=True)
                                trow += tcell
                                if first_event:
                                    tcell += self._(evt_type)
                                    if trow.attr == "":
                                        trow.attr = 'class = "BeginType"'
                                else:
                                    tcell += "&nbsp;"

                                # event date
                                tcell = Html("td", class_="ColumnDate",
                                             inline=True)
                                trow += tcell
                                date = Date.EMPTY
                                if event:
                                    date = event.get_date_object()
                                    if date and date is not Date.EMPTY:
                                        tcell += self.rlocale.get_date(date)
                                else:
                                    tcell += "&nbsp;"

                                # Gramps ID
                                trow += Html("td", class_="ColumnGRAMPSID") + (
                                    self.event_grampsid_link(event_handle,
                                                             gid, None)
                                    )

                                # Person(s) column
                                tcell = Html("td", class_="ColumnPerson")
                                trow += tcell

                                # classname can either be a person or a family
                                first_person = True

                                # get person(s) for ColumnPerson
                                sorted_list = sorted(handle_list)
                                self.complete_people(tcell, first_person,
                                                     sorted_list,
                                                     uplink=False)

                        _event_displayed.append(gid)
                        first_event = False

        # add clearline for proper styling
        # add footer section
        footer = self.write_footer(ldatec)
        body += (FULLCLEAR, footer)

        # send page ut for processing
        # and close the file
        self.xhtml_writer(eventslistpage, output_file, sio, ldatec)

    def _geteventdate(self, event_handle):
        """
        Get the event date

        @param: event_handle -- The handle for the event to use
        """
        event_date = Date.EMPTY
        event = self.r_db.get_event_from_handle(event_handle)
        if event:
            date = event.get_date_object()
            if date:

                # returns the date in YYYY-MM-DD format
                return Date(date.get_year_calendar("Gregorian"),
                            date.get_month(), date.get_day())

        # return empty date string
        return event_date

    def event_grampsid_link(self, handle, grampsid, uplink):
        """
        Create a hyperlink from event handle, but show grampsid

        @param: handle   -- The handle for the event
        @param: grampsid -- The gramps ID to display
        @param: uplink   -- If True, then "../../../" is inserted in front of
                            the result.
        """
        url = self.report.build_url_fname_html(handle, "evt", uplink)

        # return hyperlink to its caller
        return Html("a", grampsid, href=url, title=grampsid, inline=True)

    def eventpage(self, report, title, event_handle):
        """
        Creates the individual event page

        @param: report       -- The instance of the main report class for
                                this report
        @param: title        -- Is the title of the web page
        @param: event_handle -- The event handle for the database
        """
        event = report.database.get_event_from_handle(event_handle)
        BasePage.__init__(self, report, title, event.get_gramps_id())
        if not event:
            return None

        ldatec = event.get_change_time()
        event_media_list = event.get_media_list()

        self.uplink = True
        subdirs = True
        evt_type = self._(event.get_type().xml_str())
        self.page_title = "%(eventtype)s" % {'eventtype' : evt_type}
        self.bibli = Bibliography()

        output_file, sio = self.report.create_file(event_handle, "evt")
        eventpage, head, body = self.write_header(self._("Events"))

        # start event detail division
        with Html("div", class_="content", id="EventDetail") as eventdetail:
            body += eventdetail

            thumbnail = self.disp_first_img_as_thumbnail(event_media_list,
                                                         event)
            if thumbnail is not None:
                eventdetail += thumbnail

            # display page title
            eventdetail += Html("h3", self.page_title, inline=True)

            # begin eventdetail table
            with Html("table", class_="infolist eventlist") as table:
                eventdetail += table

                tbody = Html("tbody")
                table += tbody

                evt_gid = event.get_gramps_id()
                if not self.noid and evt_gid:
                    trow = Html("tr") + (
                        Html("td", self._("Gramps ID"),
                             class_="ColumnAttribute", inline=True),
                        Html("td", evt_gid,
                             class_="ColumnGRAMPSID", inline=True)
                        )
                    tbody += trow

                # get event data
                #
                # for more information: see get_event_data()
                #
                event_data = self.get_event_data(event, event_handle,
                                                 subdirs, evt_gid)

                for (label, colclass, data) in event_data:
                    if data:
                        trow = Html("tr") + (
                            Html("td", label, class_="ColumnAttribute",
                                 inline=True),
                            Html('td', data, class_="Column" + colclass)
                            )
                        tbody += trow

            # Narrative subsection
            notelist = event.get_note_list()
            notelist = self.display_note_list(notelist)
            if notelist is not None:
                eventdetail += notelist

            # get attribute list
            attrlist = event.get_attribute_list()
            if attrlist:
                attrsection, attrtable = self.display_attribute_header()
                self.display_attr_list(attrlist, attrtable)
                eventdetail += attrsection

            # event source references
            srcrefs = self.display_ind_sources(event)
            if srcrefs is not None:
                eventdetail += srcrefs

            # display additional images as gallery
            if self.create_media:
                addgallery = self.disp_add_img_as_gallery(event_media_list,
                                                          event)
                if addgallery:
                    eventdetail += addgallery

            # References list
            ref_list = self.display_bkref_list(Event, event_handle)
            if ref_list is not None:
                eventdetail += ref_list

        # add clearline for proper styling
        # add footer section
        footer = self.write_footer(ldatec)
        body += (FULLCLEAR, footer)

        # send page out for processing
        # and close the page
        self.xhtml_writer(eventpage, output_file, sio, ldatec)
