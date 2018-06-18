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
    FamilyPage - Family index page and individual Family pages
"""
#------------------------------------------------
# python modules
#------------------------------------------------
from collections import defaultdict
from decimal import getcontext
import logging

#------------------------------------------------
# Gramps module
#------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.lib import (EventType, Family)
from gramps.gen.plug.report import Bibliography
from gramps.plugins.lib.libhtml import Html

#------------------------------------------------
# specific narrative web import
#------------------------------------------------
from gramps.plugins.webreport.basepage import BasePage
from gramps.plugins.webreport.common import (get_first_letters, _KEYPERSON,
                                             alphabet_navigation, sort_people,
                                             primary_difference, first_letter,
                                             FULLCLEAR, get_index_letter)

_ = glocale.translation.sgettext
LOG = logging.getLogger(".NarrativeWeb")
getcontext().prec = 8

#################################################
#
#    creates the Family List Page and Family Pages
#
#################################################
class FamilyPages(BasePage):
    """
    This class is responsible for displaying information about the 'Family'
    database objects. It displays this information under the 'Families'
    tab. It is told by the 'add_instances' call which 'Family's to display,
    and remembers the list of Family. A single call to 'display_pages'
    displays both the Family List (Index) page and all the Family
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
        self.family_dict = defaultdict(set)
        self.familymappages = None

    def display_pages(self, title):
        """
        Generate and output the pages under the Family tab, namely the family
        index and the individual family pages.

        @param: title -- Is the title of the web page
        """
        LOG.debug("obj_dict[Family]")
        for item in self.report.obj_dict[Family].items():
            LOG.debug("    %s", str(item))

        message = _("Creating family pages...")
        index = 1
        with self.r_user.progress(_("Narrated Web Site Report"), message,
                                  len(self.report.obj_dict[Family]) + 1
                                 ) as step:
            for family_handle in self.report.obj_dict[Family]:
                step()
                index += 1
                self.familypage(self.report, title, family_handle)
            step()
            self.familylistpage(self.report, title,
                                self.report.obj_dict[Family].keys())

    def familylistpage(self, report, title, fam_list):
        """
        Create a family index

        @param: report   -- The instance of the main report class for
                            this report
        @param: title    -- Is the title of the web page
        @param: fam_list -- The handle for the place to add
        """
        BasePage.__init__(self, report, title)

        output_file, sio = self.report.create_file("families")
        familieslistpage, head, body = self.write_header(self._("Families"))
        ldatec = 0
        prev_letter = " "

        # begin Family Division
        with Html("div", class_="content", id="Relationships") as relationlist:
            body += relationlist

            # Families list page message
            msg = self._("This page contains an index of all the "
                         "families/ relationships in the "
                         "database, sorted by their family name/ surname. "
                         "Clicking on a person&#8217;s "
                         "name will take you to their "
                         "family/ relationship&#8217;s page.")
            relationlist += Html("p", msg, id="description")

            # go through all the families, and construct a dictionary of all the
            # people and the families thay are involved in. Note that the people
            # in the list may be involved in OTHER families, that are not listed
            # because they are not in the original family list.
            pers_fam_dict = defaultdict(list)
            for family_handle in fam_list:
                family = self.r_db.get_family_from_handle(family_handle)
                if family:
                    if family.get_change_time() > ldatec:
                        ldatec = family.get_change_time()
                    husband_handle = family.get_father_handle()
                    spouse_handle = family.get_mother_handle()
                    if husband_handle:
                        pers_fam_dict[husband_handle].append(family)
                    if spouse_handle:
                        pers_fam_dict[spouse_handle].append(family)

            # add alphabet navigation
            index_list = get_first_letters(self.r_db, pers_fam_dict.keys(),
                                           _KEYPERSON, rlocale=self.rlocale)
            alpha_nav = alphabet_navigation(index_list, self.rlocale)
            if alpha_nav:
                relationlist += alpha_nav

            # begin families table and table head
            with Html("table", class_="infolist relationships") as table:
                relationlist += table

                thead = Html("thead")
                table += thead

                trow = Html("tr")
                thead += trow

               # set up page columns
                trow.extend(
                    Html("th", trans, class_=colclass, inline=True)
                    for trans, colclass in [(self._("Letter"),
                                             "ColumnRowLabel"),
                                            (self._("Person"), "ColumnPartner"),
                                            (self._("Family"), "ColumnPartner"),
                                            (self._("Marriage"), "ColumnDate"),
                                            (self._("Divorce"), "ColumnDate")]
                    )

                tbody = Html("tbody")
                table += tbody

                # begin displaying index list
                ppl_handle_list = sort_people(self.r_db, pers_fam_dict.keys(),
                                              self.rlocale)
                first = True
                for (surname, handle_list) in ppl_handle_list:

                    if surname and not surname.isspace():
                        letter = get_index_letter(first_letter(surname),
                                                  index_list,
                                                  self.rlocale)
                    else:
                        letter = '&nbsp;'

                    # get person from sorted database list
                    for person_handle in sorted(
                            handle_list, key=self.sort_on_name_and_grampsid):
                        person = self.r_db.get_person_from_handle(person_handle)
                        if person:
                            family_list = person.get_family_handle_list()
                            first_family = True
                            for family_handle in family_list:
                                get_family = self.r_db.get_family_from_handle
                                family = get_family(family_handle)
                                trow = Html("tr")
                                tbody += trow

                                tcell = Html("td", class_="ColumnRowLabel")
                                trow += tcell

                                if first or primary_difference(letter,
                                                               prev_letter,
                                                               self.rlocale):
                                    first = False
                                    prev_letter = letter
                                    trow.attr = 'class="BeginLetter"'
                                    ttle = self._("Families beginning with "
                                                  "letter ")
                                    tcell += Html("a", letter, name=letter,
                                                  title=ttle + letter,
                                                  inline=True)
                                else:
                                    tcell += '&nbsp;'

                                tcell = Html("td", class_="ColumnPartner")
                                trow += tcell

                                if first_family:
                                    trow.attr = 'class ="BeginFamily"'

                                    tcell += self.new_person_link(
                                        person_handle, uplink=self.uplink)

                                    first_family = False
                                else:
                                    tcell += '&nbsp;'

                                tcell = Html("td", class_="ColumnPartner")
                                trow += tcell

                                tcell += self.family_link(
                                    family.get_handle(),
                                    self.report.get_family_name(family),
                                    family.get_gramps_id(), self.uplink)

                                # family events; such as marriage and divorce
                                # events
                                fam_evt_ref_list = family.get_event_ref_list()
                                tcell1 = Html("td", class_="ColumnDate",
                                              inline=True)
                                tcell2 = Html("td", class_="ColumnDate",
                                              inline=True)
                                trow += (tcell1, tcell2)

                                if fam_evt_ref_list:
                                    fam_evt_srt_ref_list = sorted(
                                        fam_evt_ref_list,
                                        key=self.sort_on_grampsid)
                                    for evt_ref in fam_evt_srt_ref_list:
                                        evt = self.r_db.get_event_from_handle(
                                            evt_ref.ref)
                                        if evt:
                                            evt_type = evt.get_type()
                                            if evt_type in [EventType.MARRIAGE,
                                                            EventType.DIVORCE]:

                                                cell = self.rlocale.get_date(
                                                    evt.get_date_object())
                                                if (evt_type ==
                                                        EventType.MARRIAGE):
                                                    tcell1 += cell
                                                else:
                                                    tcell1 += '&nbsp;'

                                                if (evt_type ==
                                                        EventType.DIVORCE):
                                                    tcell2 += cell
                                                else:
                                                    tcell2 += '&nbsp;'
                                else:
                                    tcell1 += '&nbsp;'
                                    tcell2 += '&nbsp;'
                                first_family = False

        # add clearline for proper styling
        # add footer section
        footer = self.write_footer(ldatec)
        body += (FULLCLEAR, footer)

        # send page out for processing
        # and close the file
        self.xhtml_writer(familieslistpage, output_file, sio, ldatec)

    def familypage(self, report, title, family_handle):
        """
        Create a family page

        @param: report        -- The instance of the main report class for
                                 this report
        @param: title         -- Is the title of the web page
        @param: family_handle -- The handle for the family to add
        """
        family = report.database.get_family_from_handle(family_handle)
        if not family:
            return
        BasePage.__init__(self, report, title, family.get_gramps_id())
        ldatec = family.get_change_time()

        self.bibli = Bibliography()
        self.uplink = True
        family_name = self.report.get_family_name(family)
        self.page_title = family_name

        self.familymappages = report.options["familymappages"]

        output_file, sio = self.report.create_file(family.get_handle(), "fam")
        familydetailpage, head, body = self.write_header(family_name)

        # begin FamilyDetaill division
        with Html("div", class_="content",
                  id="RelationshipDetail") as relationshipdetail:
            body += relationshipdetail

            # family media list for initial thumbnail
            if self.create_media:
                media_list = family.get_media_list()
                # If Event pages are not being created, then we need to display
                # the family event media here
                if not self.inc_events:
                    for evt_ref in family.get_event_ref_list():
                        event = self.r_db.get_event_from_handle(evt_ref.ref)
                        media_list += event.get_media_list()

            relationshipdetail += Html(
                "h2", self.page_title, inline=True) + (
                    Html('sup') + (Html('small') +
                                   self.get_citation_links(
                                       family.get_citation_list())))

            # display relationships
            families = self.display_family_relationships(family, None)
            if families is not None:
                relationshipdetail += families

            # display additional images as gallery
            if self.create_media and media_list:
                addgallery = self.disp_add_img_as_gallery(media_list, family)
                if addgallery:
                    relationshipdetail += addgallery

            # Narrative subsection
            notelist = family.get_note_list()
            if notelist:
                relationshipdetail += self.display_note_list(notelist)

            # display family LDS ordinance...
            family_lds_ordinance_list = family.get_lds_ord_list()
            if family_lds_ordinance_list:
                relationshipdetail += self.display_lds_ordinance(family)

            # get attribute list
            attrlist = family.get_attribute_list()
            if attrlist:
                attrsection, attrtable = self.display_attribute_header()
                self.display_attr_list(attrlist, attrtable)
                relationshipdetail += attrsection

            # source references
            srcrefs = self.display_ind_sources(family)
            if srcrefs:
                relationshipdetail += srcrefs

        # add clearline for proper styling
        # add footer section
        footer = self.write_footer(ldatec)
        body += (FULLCLEAR, footer)

        # send page out for processing
        # and close the file
        self.xhtml_writer(familydetailpage, output_file, sio, ldatec)
