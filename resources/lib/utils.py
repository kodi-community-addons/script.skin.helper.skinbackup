#!/usr/bin/python
# -*- coding: utf-8 -*-

'''Various helper methods'''

import os, sys
import xbmc
import xbmcvfs
import xbmcgui
if sys.version_info.major == 3:
    import urllib.request, urllib.parse, urllib.error
    import traceback
else:
    import urllib
    from traceback import format_exc
import unicodedata

ADDON_ID = "script.skin.helper.skinbackup"
KODI_VERSION = int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0])
if sys.version_info.major == 3:
    ADDON_DATA = 'special://profile/addon_data/%s/' % ADDON_ID
else:
    ADDON_DATA = u'special://profile/addon_data/%s/' % ADDON_ID


def log_msg(msg, loglevel=xbmc.LOGDEBUG):
    '''log to kodi logfile'''
    if sys.version_info.major < 3:
        if isinstance(msg, unicode):
            msg = msg.encode('utf-8')
    xbmc.log("Skin Helper Backup --> %s" % msg, level=loglevel)


def log_exception(modulename, exceptiondetails):
    '''helper to properly log exception details'''
    if sys.version_info.major == 3:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        log_msg("Exception details: Type: %s Value: %s Traceback: %s" % (exc_type.__name__, exc_value, ''.join(line for line in lines)), xbmc.LOGWARNING)
    else:
        log_msg(format_exc(sys.exc_info()), xbmc.LOGWARNING)

    dialog = xbmcgui.Dialog()
    dialog.notification(
        "Skin Helper Backup",
        "Error while executing, please check your kodi logfile.",
        xbmcgui.NOTIFICATION_ERROR)
    del dialog


def kodi_json(jsonmethod, params=None):
    '''get info from the kodi json api'''
    try:
        import simplejson as json
    except Exception:
        import json
    kodi_json = {}
    kodi_json["jsonrpc"] = "2.0"
    kodi_json["method"] = jsonmethod
    if not params:
        params = {}
    kodi_json["params"] = params
    kodi_json["id"] = 1
    json_response = xbmc.executeJSONRPC(try_encode(json.dumps(kodi_json)))
    json_object = json.loads(try_decode(json_response))
    result = None
    if 'result' in json_object:
        # look for correct returntype
        if isinstance(json_object['result'], dict):
            if sys.version_info.major == 3:
                for key, value in list(json_object['result'].items()):
                    if not key == "limits":
                        result = value
                        break
            else:
                for key, value in json_object['result'].iteritems():
                    if not key == "limits":
                        result = value
                        break
        else:
            return json_object['result']
    return result


def recursive_delete_dir(fullpath):
    '''helper to recursively delete a directory'''
    success = True
    if sys.version_info.major < 3:
        if not isinstance(fullpath, unicode):
            fullpath = fullpath.decode("utf-8")
    dirs, files = xbmcvfs.listdir(fullpath)
    for file in files:
        file = try_decode(file)
        success = xbmcvfs.delete(os.path.join(fullpath, file))
    for directory in dirs:
        directory = try_decode(directory)
        success = recursive_delete_dir(os.path.join(fullpath, directory))
    success = xbmcvfs.rmdir(fullpath)
    return success


def copy_file(source, destination, do_wait=False):
    '''copy a file on the filesystem, wait for the action to be completed'''
    if xbmcvfs.exists(destination):
        delete_file(destination)
    xbmcvfs.copy(source, destination)
    if do_wait:
        count = 20
        while count:
            xbmc.sleep(500)  # this first sleep is intentional
            if xbmcvfs.exists(destination):
                break
            count -= 1


def delete_file(filepath, do_wait=False):
    '''delete a file on the filesystem, wait for the action to be completed'''
    xbmcvfs.delete(filepath)
    if do_wait:
        count = 20
        while count:
            xbmc.sleep(500)  # this first sleep is intentional
            if not xbmcvfs.exists(filepath):
                break
            count -= 1


def get_clean_image(image):
    '''helper to strip all kodi tags/formatting of an image path/url'''
    if image and "image://" in image:
        image = image.replace("image://", "")
        image = urllib.unquote(try_encode(image))
        if image.endswith("/"):
            image = image[:-1]
    if sys.version_info.major < 3:
        if not isinstance(image, unicode):
            image = image.decode("utf8")
    if "music@" in image:
        # filter out embedded covers
        image = ""
    return image


def normalize_string(text):
    '''normalize string, strip all special chars'''
    text = text.replace(":", "")
    text = text.replace("/", "-")
    text = text.replace("\\", "-")
    text = text.replace("<", "")
    text = text.replace(">", "")
    text = text.replace("*", "")
    text = text.replace("?", "")
    text = text.replace('|', "")
    text = text.replace('(', "")
    text = text.replace(')', "")
    text = text.replace("\"", "")
    text = text.strip()
    text = text.rstrip('.')
    if sys.version_info.major < 3:
        if not isinstance(text, unicode):
            text = text.decode("utf-8")
    text = unicodedata.normalize('NFKD', text)
    return text


def add_tozip(src, zip_file, abs_src):
    '''helper method'''
    dirs, files = xbmcvfs.listdir(src)
    for filename in files:
        filename = try_decode(filename)
        log_msg("zipping %s" % filename)
        if sys.version_info.major == 3:
            filepath = try_decode(xbmcvfs.translatePath(os.path.join(src, filename)))
        else:
            filepath = try_decode(xbmc.translatePath(os.path.join(src, filename)))
        absname = os.path.abspath(filepath)
        arcname = absname[len(abs_src) + 1:]
        try:
            # newer python can use unicode for the files in the zip
            zip_file.write(absname, arcname)
        except Exception:
            # older python version uses utf-8 for filenames in the zip
            zip_file.write(try_encode(absname), try_encode(arcname))
    for directory in dirs:
        add_tozip(os.path.join(src, directory), zip_file, abs_src)
    return zip_file


def zip_tofile(src, dst):
    '''method to create a zip file from all files/dirs in a path'''
    #Android alternative zipfile check https://forum.kodi.tv/showthread.php?tid=219745
    if xbmc.getCondVisibility('system.platform.linux') and xbmc.getCondVisibility('system.platform.android') and sys.version_info.major < 3:
        from . import zipfile
    else:
        import zipfile
    zip_file = zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED)
    if sys.version_info.major == 3:
        abs_src = os.path.abspath(try_decode(xbmcvfs.translatePath(src)))
    else:
        abs_src = os.path.abspath(try_decode(xbmc.translatePath(src)))
    zip_file = add_tozip(src, zip_file, abs_src)
    zip_file.close()


def unzip_fromfile(zip_path, dest_path):
    '''method to unzip a zipfile to a destination path'''
    import shutil
    #Android alternative zipfile check https://forum.kodi.tv/showthread.php?tid=219745
    if xbmc.getCondVisibility('system.platform.linux') and xbmc.getCondVisibility('system.platform.android') and sys.version_info.major < 3:
        from . import zipfile
    else:
        import zipfile
    if sys.version_info.major == 3:
        zip_path = try_decode(xbmcvfs.translatePath(zip_path))
        dest_path = try_decode(xbmcvfs.translatePath(dest_path))
    else:
        zip_path = try_decode(xbmc.translatePath(zip_path))
        dest_path = try_decode(xbmc.translatePath(dest_path))
    log_msg("START UNZIP of file %s  to path %s " % (zip_path, dest_path))
    zip_file = zipfile.ZipFile(zip_path, 'r')
    for fileinfo in zip_file.infolist():
        filename = fileinfo.filename
        if sys.version_info.major < 3:
            if not isinstance(filename, unicode):
                filename = filename.decode("utf-8")
        log_msg("unzipping: " + filename)
        splitter = None
        if "\\" in filename:
            xbmcvfs.mkdirs(os.path.join(dest_path, filename.rsplit("\\", 1)[0]))
            splitter = "\\"
        elif "/" in filename:
            xbmcvfs.mkdirs(os.path.join(dest_path, filename.rsplit("/", 1)[0]))
            splitter = "/"
        filename = os.path.join(dest_path, filename)
        if not (splitter and filename.endswith(splitter)):
            try:
                # newer python uses unicode
                outputfile = open(filename, "wb")
            except Exception:
                # older python uses utf-8
                outputfile = open(try_encode(filename), "wb")
            # use shutil to support non-ascii formatted files in the zip
            shutil.copyfileobj(zip_file.open(fileinfo.filename), outputfile)
            outputfile.close()
    zip_file.close()
    log_msg("UNZIP DONE of file %s  to path %s " % (zip_path, dest_path))


def get_skin_name():
    ''' get the skin name filtering out any beta prefixes and such.'''
    skin_name = try_decode(xbmc.getSkinDir())
    skin_name = skin_name.replace("skin.", "")
    skin_name = skin_name.replace(".kryptonbeta", "")
    skin_name = skin_name.replace(".jarvisbeta", "")
    skin_name = skin_name.replace(".leiabeta", "")
    return skin_name


def try_encode(text, encoding="utf-8"):
    '''helper to encode a string to utf-8'''
    if sys.version_info.major == 3:
        return text
    else:
        try:
            return text.encode(encoding, "ignore")
        except Exception:
            return text


def try_decode(text, encoding="utf-8"):
    '''helper to decode a string into unicode'''
    if sys.version_info.major == 3:
        return text
    else:
        try:
            return text.decode(encoding, "ignore")
        except Exception:
            return text

