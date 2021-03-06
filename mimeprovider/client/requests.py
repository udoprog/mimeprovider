"""
A mimeprovider client based on requests.
"""
from __future__ import absolute_import

import sys
import logging

log = logging.getLogger(__name__)

import urlparse

import requests
import werkzeug.http

from mimeprovider.exceptions import MimeValidationError

from mimeprovider.client import Client

DEFAULT_HEADERS = {
    "Accept": "*/*"
}


class ClientException(Exception):
    pass


class RequestsClient(Client):
    def __init__(self, mimetypes, mimeobjects, url, **kw):
        # mimetype do document type mappings.
        self.mimetypes = mimetypes

        # object to document type mappings.
        self.mimeobjects = mimeobjects

        url = urlparse.urlparse(url)

        if url.port:
            self.host = "{0}:{1}".format(url.hostname, url.port)
        else:
            self.host = url.hostname

        if not url.scheme:
            self.scheme = "https"
        else:
            self.scheme = url.scheme

        headers = dict(DEFAULT_HEADERS)
        headers.update(kw.pop("headers", {}))

        self.session = requests.session(
            headers=headers,
            **kw)

    def request(self, method, uri, **kw):
        """
        The money maker.
        """
        expect = kw.pop("expect", [])
        mime_body = kw.pop("mime_body", None)

        headers = kw.pop("headers", {})
        data = kw.pop("data", None)

        if mime_body:
            mimevalues = self.mimeobjects.get(mime_body.__class__)

            if not mimevalues:
                raise ClientException(
                    ("Cannot handle object of type "
                     "{0!r}").format(mime_body.__class__))

            mapping = mimevalues[0]

            document_type, mimetype, validator = mapping

            data = document_type.render(validator, mime_body)
            headers["Content-Type"] = mimetype

        if uri[0] != '/':
            uri = '/' + uri

        url = "{self.scheme}://{self.host}{uri}".format(self=self, uri=uri)

        response = self.session.request(
            method, url,
            headers=headers,
            data=data,
            **kw)

        content_type = response.headers.get("Content-Type")

        if content_type is None or not response.content:
            return response, None

        mimetype, opts = werkzeug.http.parse_options_header(content_type)

        if mimetype not in self.mimetypes:
            raise ClientException(
                "Cannot handle response type: {0}".format(mimetype))

        document_type, document_class, validator = self.mimetypes.get(mimetype)

        if expect and document_class not in expect:
            raise ClientException(
                "Unexpected response type: {0}".format(mimetype))

        try:
            obj = document_type.parse(validator,
                                      document_class,
                                      response.content)
        except MimeValidationError as e:
            raise ClientException(
                "Response format invalid: {0}".format(str(e)))
        except:
            log.error(
                "Failed to parse content of type: {0}".format(mimetype),
                exc_info=sys.exc_info())
            raise ClientException(
                "Failed to parse content of type: {0}".format(mimetype))

        return response, obj
