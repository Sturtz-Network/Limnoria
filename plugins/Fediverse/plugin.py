###
# Copyright (c) 2020, Valentin Lorentz
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import re
import json
import importlib
import urllib.parse

from supybot import conf, utils, plugins, ircutils, callbacks, httpserver
from supybot.commands import *
from supybot.i18n import PluginInternationalization

_ = PluginInternationalization("Fediverse")

from . import activitypub as ap

importlib.reload(ap)


_username_re = re.compile("@(?P<localuser>[^@]+)@(?P<hostname>[^@]+)")


class FediverseHttp(httpserver.SupyHTTPServerCallback):
    name = "minimal ActivityPub server"
    defaultResponse = _(
        """
    You shouldn't be here, this subfolder is not for you. Go back to the
    index and try out other plugins (if any)."""
    )

    def doGetOrHead(self, handler, path, write_content):
        if path == "/instance_actor":
            self.instance_actor(write_content)
        else:
            assert False, repr(path)

    def doWellKnown(self, handler, path):
        actor_url = ap.get_instance_actor_url()
        instance_hostname = urllib.parse.urlsplit(actor_url).hostname
        instance_account = "acct:%s@%s" % (
            instance_hostname,
            instance_hostname,
        )
        if path == "/webfinger?resource=%s" % instance_account:
            headers = {"Content-Type": "application/jrd+json"}
            content = {
                "subject": instance_account,
                "links": [
                    {
                        "rel": "self",
                        "type": "application/activity+json",
                        "href": actor_url,
                    }
                ],
            }
            return (200, headers, json.dumps(content).encode())
        else:
            return None

    def instance_actor(self, write_content):
        self.send_response(200)
        self.send_header("Content-type", ap.ACTIVITY_MIMETYPE)
        self.end_headers()
        if not write_content:
            return
        pem = ap.get_public_key_pem()
        actor_url = ap.get_instance_actor_url()
        hostname = urllib.parse.urlparse(hostname).hostname
        actor = {
            "@context": [
                "https://www.w3.org/ns/activitystreams",
                "https://w3id.org/security/v1",
            ],
            "id": actor_url,
            "preferredUsername": hostname,
            "type": "Person",
            "publicKey": {
                "id": actor_url + "#main-key",
                "owner": actor_url,
                "publicKeyPem": pem.decode(),
            },
            "inbox": actor_url + "/inbox",
        }
        self.wfile.write(json.dumps(actor).encode())


class Fediverse(callbacks.Plugin):
    """Fetches information from ActivityPub servers."""

    threaded = True

    def __init__(self, irc):
        super().__init__(irc)
        self._startHttp()

    def _startHttp(self):
        callback = FediverseHttp()
        callback._plugin = self
        httpserver.hook("fediverse", callback)

    def die(self):
        self._stopHttp()
        super().die()

    def _stopHttp(self):
        httpserver.unhook("fediverse")

    @wrap(["somethingWithoutSpaces"])
    def profile(self, irc, msg, args, username):
        """<@user@instance>

        Returns generic information on the account @user@instance."""
        match = _username_re.match(username)
        if not match:
            irc.errorInvalid("fediverse username", username)
        localuser = match.group("localuser")
        hostname = match.group("hostname")

        try:
            actor = ap.get_actor(localuser, hostname)
        except ap.ActorNotFound as e:
            # Usually a 404
            irc.error("Unknown user %s." % username, Raise=True)

        irc.reply(
            _("\x02%s\x02 (@%s@%s): %s")
            % (
                actor["name"],
                actor["preferredUsername"],
                hostname,
                utils.web.htmlToText(actor["summary"], tagReplace=""),
            )
        )

    '''
    @wrap(['somethingWithoutSpaces'])
    def post(self, irc, msg, args, username):
        """<@user@instance>

        Returns generic information on the account @user@instance."""
        match = _username_re.match(username)
        if not match:
            irc.errorInvalid('fediverse username', username)
        localuser = match.group('localuser')
        hostname = match.group('hostname')

        instance_actor = ap.get_instance_actor_url()
        instance_hostname = urllib.parse.urlparse(
            conf.supybot.servers.http.publicUrl()).hostname
        doc = {
            "@context": "https://www.w3.org/ns/activitystreams",

            "id": "https://%s/create-hello-world" % instance_hostname,
            "type": "Create",
            "actor": instance_actor,

            "object": {
                    "id": "https://%s/hello-world" % instance_hostname,
                    "type": "Note",
                    "published": "2018-06-23T17:17:11Z",
                    "attributedTo": instance_actor,
                    "content": "<p>Hello world</p>",
                    "to": "https://www.w3.org/ns/activitystreams#Public"
            }
        }

        ap._signed_request(
            url='https://%s/inbox' % hostname,
            headers={},
            data=json.dumps(doc),
        )'''


Class = Fediverse


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
