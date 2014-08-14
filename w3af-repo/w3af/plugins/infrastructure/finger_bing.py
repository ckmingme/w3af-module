"""
finger_bing.py

Copyright 2006 Andres Riancho

This file is part of w3af, http://w3af.org/ .

w3af is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation version 2 of the License.

w3af is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with w3af; if not, write to the Free Software
Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""
import w3af.core.controllers.output_manager as om
import w3af.core.data.parsers.parser_cache as parser_cache

from w3af.core.controllers.plugins.infrastructure_plugin import InfrastructurePlugin
from w3af.core.controllers.exceptions import BaseFrameworkException, ScanMustStopOnUrlError
from w3af.core.controllers.exceptions import RunOnce
from w3af.core.controllers.misc.decorators import runonce
from w3af.core.controllers.misc.is_private_site import is_private_site

from w3af.core.data.search_engines.bing import bing as bing
from w3af.core.data.options.opt_factory import opt_factory
from w3af.core.data.options.option_list import OptionList
from w3af.core.data.kb.info import Info


class finger_bing(InfrastructurePlugin):
    """
    Search Bing to get a list of users for a domain.
    :author: Andres Riancho (andres.riancho@gmail.com)
    """

    def __init__(self):
        InfrastructurePlugin.__init__(self)

        # Internal variables
        self._accounts = []

        # User configured
        self._result_limit = 300

    @runonce(exc_class=RunOnce)
    def discover(self, fuzzable_request):
        """
        :param fuzzable_request: A fuzzable_request instance that contains
        (among other things) the URL to test.
        """
        if not is_private_site(fuzzable_request.get_url().get_domain()):
            bingSE = bing(self._uri_opener)
            self._domain = fuzzable_request.get_url().get_domain()
            self._domain_root = fuzzable_request.get_url().get_root_domain()

            results = bingSE.get_n_results(
                '@' + self._domain_root, self._result_limit)

            #   Send the requests using threads:
            self.worker_pool.map(self._find_accounts, results)

    def _find_accounts(self, page):
        """
        Finds emails in bing result.

        :return: A list of valid accounts
        """
        try:
            url = page.URL
            om.out.debug('Searching for emails in: %s' % url)

            grep = True if self._domain == url.get_domain() else False
            response = self._uri_opener.GET(page.URL, cache=True,
                                            grep=grep)
        except ScanMustStopOnUrlError:
            # Just ignore it
            pass
        except BaseFrameworkException, w3:
            msg = 'ExtendedUrllib exception raised while fetching page in finger_bing,'
            msg += ' error description: ' + str(w3)
            om.out.debug(msg)
        else:

            # I have the response object!
            try:
                document_parser = parser_cache.dpc.get_document_parser_for(response)
            except BaseFrameworkException:
                # Failed to find a suitable parser for the document
                pass
            else:
                # Search for email addresses
                for mail in document_parser.get_emails(self._domain_root):
                    if mail not in self._accounts:
                        self._accounts.append(mail)
                        
                        desc = 'The mail account: "%s" was found at: "%s".'
                        desc = desc % (mail, page.URL)

                        i = Info('Email account', desc, response.id,
                                 self.get_name())
                        i.set_url(page.URL)
                        i['mail'] = mail
                        i['user'] = mail.split('@')[0]
                        i['url_list'] = set([page.URL, ])
                        
                        self.kb_append('emails', 'emails', i)
                        self.kb_append('finger_bing', 'emails', i)

    def get_options(self):
        """
        :return: A list of option objects for this plugin.
        """
        ol = OptionList()

        d1 = 'Fetch the first "result_limit" results from the Bing search'
        o = opt_factory('result_limit', self._result_limit, d1, 'integer')
        ol.add(o)

        return ol

    def set_options(self, options_list):
        """
        This method sets all the options that are configured using the user interface
        generated by the framework using the result of get_options().

        :param OptionList: A dictionary with the options for the plugin.
        :return: No value is returned.
        """
        self._result_limit = options_list['result_limit'].get_value()

    def get_long_desc(self):
        """
        :return: A DETAILED description of the plugin functions and features.
        """
        return """
        This plugin finds mail addresses in Bing search engine.

        One configurable parameter exist:
            - result_limit

        This plugin searches Bing for : "@domain.com", requests all search results
        and parses them in order to find new mail addresses.
        """
