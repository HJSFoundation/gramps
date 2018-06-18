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
    MediaPage - Media index page and individual Media pages
"""
#------------------------------------------------
# python modules
#------------------------------------------------
import gc
import os
import shutil
import tempfile
from collections import defaultdict
from decimal import getcontext
import logging

#------------------------------------------------
# Gramps module
#------------------------------------------------
from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.lib import (Date, Media)
from gramps.gen.plug.report import Bibliography
from gramps.gen.utils.file import media_path_full
from gramps.gen.utils.thumbnails import run_thumbnailer
from gramps.gen.utils.image import image_size # , resize_to_jpeg_buffer
from gramps.plugins.lib.libhtml import Html

#------------------------------------------------
# specific narrative web import
#------------------------------------------------
from gramps.plugins.webreport.basepage import BasePage
from gramps.plugins.webreport.common import (FULLCLEAR, _WRONGMEDIAPATH,
                                             html_escape)

_ = glocale.translation.sgettext
LOG = logging.getLogger(".NarrativeWeb")
getcontext().prec = 8

#################################################
#
#    creates the Media List Page and Media Pages
#
#################################################
class MediaPages(BasePage):
    """
    This class is responsible for displaying information about the 'Media'
    database objects. It displays this information under the 'Individuals'
    tab. It is told by the 'add_instances' call which 'Media's to display,
    and remembers the list of persons. A single call to 'display_pages'
    displays both the Individual List (Index) page and all the Individual
    pages.

    The base class 'BasePage' is initialised once for each page that is
    displayed.
    """
    def __init__(self, report):
        """
        @param: report -- The instance of the main report class for this report
        """
        BasePage.__init__(self, report, title="")
        self.media_dict = defaultdict(set)
        self.unused_media_handles = []

    def display_pages(self, title):
        """
        Generate and output the pages under the Media tab, namely the media
        index and the individual media pages.

        @param: title -- Is the title of the web page
        """
        LOG.debug("obj_dict[Media]")
        for item in self.report.obj_dict[Media].items():
            LOG.debug("    %s", str(item))
        if self.create_unused_media:
            media_count = len(self.r_db.get_media_handles())
        else:
            media_count = len(self.report.obj_dict[Media])
        message = _("Creating media pages")
        with self.r_user.progress(_("Narrated Web Site Report"), message,
                                  media_count + 1
                                 ) as step:
            # bug 8950 : it seems it's better to sort on desc + gid.
            def sort_by_desc_and_gid(obj):
                """
                Sort by media description and gramps ID
                """
                return (obj.desc.lower(), obj.gramps_id)

            self.unused_media_handles = []
            if self.create_unused_media:
                # add unused media
                media_list = self.r_db.get_media_handles()
                for media_ref in media_list:
                    if media_ref not in self.report.obj_dict[Media]:
                        self.unused_media_handles.append(media_ref)
                self.unused_media_handles = sorted(
                    self.unused_media_handles,
                    key=lambda x: sort_by_desc_and_gid(
                        self.r_db.get_media_from_handle(x)))

            sorted_media_handles = sorted(
                self.report.obj_dict[Media].keys(),
                key=lambda x: sort_by_desc_and_gid(
                    self.r_db.get_media_from_handle(x)))
            prev = None
            total = len(sorted_media_handles)
            index = 1
            for handle in sorted_media_handles:
                gc.collect() # Reduce memory usage when there are many images.
                if index == media_count:
                    next_ = None
                elif index < total:
                    next_ = sorted_media_handles[index]
                elif len(self.unused_media_handles) > 0:
                    next_ = self.unused_media_handles[0]
                else:
                    next_ = None
                self.mediapage(self.report, title,
                               handle, (prev, next_, index, media_count))
                prev = handle
                step()
                index += 1

            total = len(self.unused_media_handles)
            idx = 1
            total_m = len(sorted_media_handles)
            prev = sorted_media_handles[total_m-1] if total_m > 0 else 0
            if total > 0:
                for media_handle in self.unused_media_handles:
                    media = self.r_db.get_media_from_handle(media_handle)
                    gc.collect() # Reduce memory usage when many images.
                    if index == media_count:
                        next_ = None
                    else:
                        next_ = self.unused_media_handles[idx]
                    self.mediapage(self.report, title,
                                   media_handle,
                                   (prev, next_, index, media_count))
                    prev = media_handle
                    step()
                    index += 1
                    idx += 1

        self.medialistpage(self.report, title, sorted_media_handles)

    def medialistpage(self, report, title, sorted_media_handles):
        """
        Generate and output the Media index page.

        @param: report               -- The instance of the main report class
                                        for this report
        @param: title                -- Is the title of the web page
        @param: sorted_media_handles -- A list of the handles of the media to be
                                        displayed sorted by the media title
        """
        BasePage.__init__(self, report, title)

        output_file, sio = self.report.create_file("media")
        # save the media file name in case we create unused media pages
        self.cur_fname = self.report.cur_fname
        medialistpage, head, body = self.write_header(self._('Media'))

        ldatec = 0
        # begin gallery division
        with Html("div", class_="content", id="Gallery") as medialist:
            body += medialist

            msg = self._("This page contains an index of all the media objects "
                         "in the database, sorted by their title. Clicking on "
                         "the title will take you to that "
                         "media object&#8217;s page.  "
                         "If you see media size dimensions "
                         "above an image, click on the "
                         "image to see the full sized version.  ")
            medialist += Html("p", msg, id="description")

            # begin gallery table and table head
            with Html("table",
                      class_="infolist primobjlist gallerylist") as table:
                medialist += table

                # begin table head
                thead = Html("thead")
                table += thead

                trow = Html("tr")
                thead += trow

                trow.extend(
                    Html("th", trans, class_=colclass, inline=True)
                    for trans, colclass in [("&nbsp;", "ColumnRowLabel"),
                                            (self._("Media | Name"),
                                             "ColumnName"),
                                            (self._("Date"), "ColumnDate"),
                                            (self._("Mime Type"), "ColumnMime")]
                )

                # begin table body
                tbody = Html("tbody")
                table += tbody

                index = 1
                if self.create_unused_media:
                    media_count = len(self.r_db.get_media_handles())
                else:
                    media_count = len(self.report.obj_dict[Media])
                message = _("Creating list of media pages")
                with self.r_user.progress(_("Narrated Web Site Report"),
                                          message, media_count + 1
                                 ) as step:
                    for media_handle in sorted_media_handles:
                        media = self.r_db.get_media_from_handle(media_handle)
                        if media:
                            if media.get_change_time() > ldatec:
                                ldatec = media.get_change_time()
                            title = media.get_description() or "[untitled]"

                            trow = Html("tr")
                            tbody += trow

                            media_data_row = [
                                [index, "ColumnRowLabel"],
                                [self.media_ref_link(media_handle,
                                                     title), "ColumnName"],
                                [self.rlocale.get_date(media.get_date_object()),
                                 "ColumnDate"],
                                [media.get_mime_type(), "ColumnMime"]]

                            trow.extend(
                                Html("td", data, class_=colclass)
                                for data, colclass in media_data_row
                            )
                        step()
                        index += 1

                    def sort_by_desc_and_gid(obj):
                        """
                        Sort by media description and gramps ID
                        """
                        return (obj.desc, obj.gramps_id)

                    idx = 1
                    prev = None
                    total = len(self.unused_media_handles)
                    if total > 0:
                        trow += Html("tr")
                        trow.extend(
                            Html("td", Html("h4", " "), inline=True) +
                            Html("td",
                                 Html("h4",
                                      self._("Below unused media objects"),
                                      inline=True),
                                 class_="") +
                            Html("td", Html("h4", " "), inline=True) +
                            Html("td", Html("h4", " "), inline=True)
                        )
                        for media_handle in self.unused_media_handles:
                            media = self.r_db.get_media_from_handle(media_handle)
                            gc.collect() # Reduce memory usage when many images.
                            if idx == total:
                                next_ = None
                            else:
                                self.unused_media_handles[idx]
                            trow += Html("tr")
                            media_data_row = [
                                [index, "ColumnRowLabel"],
                                [self.media_ref_link(media_handle,
                                                     media.get_description()),
                                 "ColumnName"],
                                [self.rlocale.get_date(media.get_date_object()),
                                 "ColumnDate"],
                                [media.get_mime_type(), "ColumnMime"]]
                            trow.extend(
                                Html("td", data, class_=colclass)
                                for data, colclass in media_data_row
                            )
                            prev = media_handle
                            step()
                            index += 1
                            idx += 1

        # add footer section
        # add clearline for proper styling
        footer = self.write_footer(ldatec)
        body += (FULLCLEAR, footer)

        # send page out for processing
        # and close the file
        self.report.cur_fname = self.cur_fname
        self.xhtml_writer(medialistpage, output_file, sio, ldatec)

    def media_ref_link(self, handle, name, uplink=False):
        """
        Create a reference link to a media

        @param: handle -- The media handle
        @param: name   -- The name to use for the link
        @param: uplink -- If True, then "../../../" is inserted in front of the
                          result.
        """
        # get media url
        url = self.report.build_url_fname_html(handle, "img", uplink)

        # get name
        name = html_escape(name)

        # begin hyper link
        hyper = Html("a", name, href=url, title=name)

        # return hyperlink to its callers
        return hyper

    def mediapage(self, report, title, media_handle, info):
        """
        Generate and output an individual Media page.

        @param: report       -- The instance of the main report class
                                for this report
        @param: title        -- Is the title of the web page
        @param: media_handle -- The media handle to use
        @param: info         -- A tuple containing the media handle for the
                                next and previous media, the current page
                                number, and the total number of media pages
        """
        media = report.database.get_media_from_handle(media_handle)
        BasePage.__init__(self, report, title, media.gramps_id)
        (prev, next_, page_number, total_pages) = info

        ldatec = media.get_change_time()

        # get media rectangles
        _region_items = self.media_ref_rect_regions(media_handle)

        output_file, sio = self.report.create_file(media_handle, "img")
        self.uplink = True

        self.bibli = Bibliography()

        # get media type to be used primarily with "img" tags
        mime_type = media.get_mime_type()
        #mtype = get_description(mime_type)

        if mime_type:
            #note_only = False
            newpath = self.copy_source_file(media_handle, media)
            target_exists = newpath is not None
        else:
            #note_only = True
            target_exists = False

        self.copy_thumbnail(media_handle, media)
        self.page_title = media.get_description()
        esc_page_title = html_escape(self.page_title)
        (mediapage, head,
         body) = self.write_header("%s - %s" % (self._("Media"),
                                                self.page_title))

        # if there are media rectangle regions, attach behaviour style sheet
        if _region_items:

            fname = "/".join(["css", "behaviour.css"])
            url = self.report.build_url_fname(fname, None, self.uplink)
            head += Html("link", href=url, type="text/css",
                         media="screen", rel="stylesheet")

        # begin MediaDetail division
        with Html("div", class_="content", id="GalleryDetail") as mediadetail:
            body += mediadetail

            # media navigation
            with Html("div", id="GalleryNav", role="navigation") as medianav:
                mediadetail += medianav
                if prev:
                    medianav += self.media_nav_link(prev,
                                                    self._("Previous"), True)
                data = self._('%(strong1_strt)s%(page_number)d%(strong_end)s '
                              'of %(strong2_strt)s%(total_pages)d%(strong_end)s'
                             ) % {'strong1_strt' :
                                  '<strong id="GalleryCurrent">',
                                  'strong2_strt' : '<strong id="GalleryTotal">',
                                  'strong_end' : '</strong>',
                                  'page_number' : page_number,
                                  'total_pages' : total_pages}
                medianav += Html("span", data, id="GalleryPages")
                if next_:
                    medianav += self.media_nav_link(next_, self._("Next"), True)

            # missing media error message
            errormsg = self._("The file has been moved or deleted.")

            # begin summaryarea division
            with Html("div", id="summaryarea") as summaryarea:
                mediadetail += summaryarea
                if mime_type:
                    if mime_type.startswith("image"):
                        if not target_exists:
                            with Html("div", id="MediaDisplay") as mediadisplay:
                                summaryarea += mediadisplay
                                mediadisplay += Html("span", errormsg,
                                                     class_="MissingImage")

                        else:
                            # Check how big the image is relative to the
                            # requested 'initial' image size.
                            # If it's significantly bigger, scale it down to
                            # improve the site's responsiveness. We don't want
                            # the user to have to await a large download
                            # unnecessarily. Either way, set the display image
                            # size as requested.
                            orig_image_path = media_path_full(self.r_db,
                                                              media.get_path())
                            #mtime = os.stat(orig_image_path).st_mtime
                            (width, height) = image_size(orig_image_path)
                            max_width = self.report.options[
                                'maxinitialimagewidth']
                            max_height = self.report.options[
                                'maxinitialimageheight']
                            if width != 0 and height != 0:
                                scale_w = (float(max_width)/width) or 1
                                           # the 'or 1' is so that a max of
                                           # zero is ignored
                                scale_h = (float(max_height)/height) or 1
                            else:
                                scale_w = 1.0
                                scale_h = 1.0
                            scale = min(scale_w, scale_h, 1.0)
                            new_width = int(width*scale)
                            new_height = int(height*scale)

                            # TODO. Convert disk path to URL.
                            url = self.report.build_url_fname(orig_image_path,
                                                              None, self.uplink)
                            with Html("div", id="GalleryDisplay",
                                      style='width: %dpx; height: %dpx' % (
                                          new_width,
                                          new_height)) as mediadisplay:
                                summaryarea += mediadisplay

                                # Feature #2634; display the mouse-selectable
                                # regions. See the large block at the top of
                                # this function where the various regions are
                                # stored in _region_items
                                if _region_items:
                                    ordered = Html("ol", class_="RegionBox")
                                    mediadisplay += ordered
                                    while len(_region_items) > 0:
                                        (name, coord_x, coord_y,
                                         width, height, linkurl
                                        ) = _region_items.pop()
                                        ordered += Html(
                                            "li",
                                            style="left:%d%%; "
                                                  "top:%d%%; "
                                                  "width:%d%%; "
                                                  "height:%d%%;" % (
                                                      coord_x, coord_y,
                                                      width, height)) + (
                                                          Html("a", name,
                                                               href=linkurl)
                                                          )

                                # display the image
                                if orig_image_path != newpath:
                                    url = self.report.build_url_fname(
                                        newpath, None, self.uplink)
                                mediadisplay += Html("a", href=url) + (
                                    Html("img", width=new_width,
                                         height=new_height, src=url,
                                         alt=esc_page_title)
                                )
                    else:
                        dirname = tempfile.mkdtemp()
                        thmb_path = os.path.join(dirname, "document.png")
                        if run_thumbnailer(mime_type,
                                           media_path_full(self.r_db,
                                                           media.get_path()),
                                           thmb_path, 320):
                            try:
                                path = self.report.build_path(
                                    "preview", media.get_handle())
                                npath = os.path.join(path, media.get_handle())
                                npath += ".png"
                                self.report.copy_file(thmb_path, npath)
                                path = npath
                                os.unlink(thmb_path)
                            except EnvironmentError:
                                path = os.path.join("images", "document.png")
                        else:
                            path = os.path.join("images", "document.png")
                        os.rmdir(dirname)

                        with Html("div", id="GalleryDisplay") as mediadisplay:
                            summaryarea += mediadisplay

                            img_url = self.report.build_url_fname(path,
                                                                  None,
                                                                  self.uplink)
                            if target_exists:
                                # TODO. Convert disk path to URL
                                url = self.report.build_url_fname(newpath,
                                                                  None,
                                                                  self.uplink)
                                hyper = Html("a", href=url,
                                             title=esc_page_title) + (
                                                 Html("img", src=img_url,
                                                      alt=esc_page_title)
                                                 )
                                mediadisplay += hyper
                            else:
                                mediadisplay += Html("span", errormsg,
                                                     class_="MissingImage")
                else:
                    with Html("div", id="GalleryDisplay") as mediadisplay:
                        summaryarea += mediadisplay
                        url = self.report.build_url_image("document.png",
                                                          "images", self.uplink)
                        mediadisplay += Html("img", src=url,
                                             alt=esc_page_title,
                                             title=esc_page_title)

                # media title
                title = Html("h3", html_escape(self.page_title.strip()),
                             inline=True)
                summaryarea += title

                # begin media table
                with Html("table", class_="infolist gallery") as table:
                    summaryarea += table

                    # Gramps ID
                    media_gid = media.gramps_id
                    if not self.noid and media_gid:
                        trow = Html("tr") + (
                            Html("td", self._("Gramps ID"),
                                 class_="ColumnAttribute",
                                 inline=True),
                            Html("td", media_gid, class_="ColumnValue",
                                 inline=True)
                            )
                        table += trow

                    # mime type
                    if mime_type:
                        trow = Html("tr") + (
                            Html("td", self._("File Type"),
                                 class_="ColumnAttribute",
                                 inline=True),
                            Html("td", mime_type, class_="ColumnValue",
                                 inline=True)
                            )
                        table += trow

                    # media date
                    date = media.get_date_object()
                    if date and date is not Date.EMPTY:
                        trow = Html("tr") + (
                            Html("td", self._("Date"), class_="ColumnAttribute",
                                 inline=True),
                            Html("td", self.rlocale.get_date(date),
                                 class_="ColumnValue",
                                 inline=True)
                            )
                        table += trow

            # get media notes
            notelist = self.display_note_list(media.get_note_list())
            if notelist is not None:
                mediadetail += notelist

            # get attribute list
            attrlist = media.get_attribute_list()
            if attrlist:
                attrsection, attrtable = self.display_attribute_header()
                self.display_attr_list(attrlist, attrtable)
                mediadetail += attrsection

            # get media sources
            srclist = self.display_media_sources(media)
            if srclist is not None:
                mediadetail += srclist

            # get media references
            reflist = self.display_bkref_list(Media, media_handle)
            if reflist is not None:
                mediadetail += reflist

        # add clearline for proper styling
        # add footer section
        footer = self.write_footer(ldatec)
        body += (FULLCLEAR, footer)

        # send page out for processing
        # and close the file
        self.xhtml_writer(mediapage, output_file, sio, ldatec)

    def media_nav_link(self, handle, name, uplink=False):
        """
        Creates the Media Page Navigation hyperlinks for Next and Prev
        """
        url = self.report.build_url_fname_html(handle, "img", uplink)
        name = html_escape(name)
        return Html("a", name, name=name, id=name, href=url,
                    title=name, inline=True)

    def display_media_sources(self, photo):
        """
        Display media sources

        @param: photo  -- The source object (image, pdf, ...)
        """
        list(map(
            lambda i: self.bibli.add_reference(
                self.r_db.get_citation_from_handle(i)),
            photo.get_citation_list()))
        sourcerefs = self.display_source_refs(self.bibli)

        # return source references to its caller
        return sourcerefs

    def copy_source_file(self, handle, photo):
        """
        Copy source file in the web tree.

        @param: handle -- Handle of the source
        @param: photo  -- The source object (image, pdf, ...)
        """
        ext = os.path.splitext(photo.get_path())[1]
        to_dir = self.report.build_path('images', handle)
        newpath = os.path.join(to_dir, handle) + ext

        fullpath = media_path_full(self.r_db, photo.get_path())
        if not os.path.isfile(fullpath):
            _WRONGMEDIAPATH.append([photo.get_gramps_id(), fullpath])
            return None
        try:
            mtime = os.stat(fullpath).st_mtime
            if self.report.archive:
                self.report.archive.add(fullpath, str(newpath))
            else:
                to_dir = os.path.join(self.html_dir, to_dir)
                if not os.path.isdir(to_dir):
                    os.makedirs(to_dir)
                new_file = os.path.join(self.html_dir, newpath)
                shutil.copyfile(fullpath, new_file)
                os.utime(new_file, (mtime, mtime))
            return newpath
        except (IOError, OSError) as msg:
            error = _("Missing media object:"
                     ) + "%s (%s)" % (photo.get_description(),
                                      photo.get_gramps_id())
            self.r_user.warn(error, str(msg))
            return None
