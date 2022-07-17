"""
The module for interaction with AD
"""
import logging
from typing import Any

import ldap
from ldap.controls import SimplePagedResultsControl
from ldap.ldapobject import SimpleLDAPObject


class ADInterface:
    """
    The class for communication with AD
    """
    def __init__(self, hostname: str, base_dn: str, user_dn: str, password: str) -> None:
        self.__hostname = hostname
        self.__base_dn = base_dn
        self.__user_dn = user_dn
        self.__password = password

    def __init_connection(self) -> SimpleLDAPObject:
        connection = f'ldap://{self.__hostname}:3268'
        logging.debug('Init ldap connection to %s', connection)
        ldap_conn = ldap.initialize(connection)
        ldap_conn.simple_bind_s(self.__user_dn, self.__password)
        return ldap_conn

    def __search_in_ad(
        self,
        base_dn: str,
        search_filter: str,
        attrs: tuple[str, ...] = ('userPrincipalName', 'sAMAccountName'),
    ) -> list[tuple[Any, Any, list[Any]]]:
        """
        Searching in AD
        Args:
            base_dn (str): Path for searching
            search_filter (str): Filter for searching

        Returns:
            list[tuple[Any, Any, list[Any]]] | None: The result of searcging
        """
        logging.debug('Search in AD %s', locals())

        ldap_conn = self.__init_connection()

        search_scope = ldap.SCOPE_SUBTREE # pylint: disable=no-member
        cookie = ''
        page_size = 1000
        criticality = True
        results = []
        first_pass = True
        pg_ctrl = SimplePagedResultsControl(criticality, page_size, cookie)

        while first_pass or pg_ctrl.cookie:
            first_pass = False
            msgid = ldap_conn.search_ext(base_dn, search_scope, search_filter, attrs, serverctrls=[pg_ctrl])

            _, data, msgid, serverctrls = ldap_conn.result3(msgid)
            pg_ctrl.cookie = serverctrls[0].cookie
            results.extend(data)
        return results

    def get_users(self) -> list[tuple[Any, Any, list[Any]]]:
        """
        Get all users
        """
        return self.__search_in_ad(self.__base_dn, 'objectClass=user')

    def get_no_exp_pass_users(self) -> list[Any]:
        """
        Get users with no expired passwords
        """
        return self.__search_in_ad(
            self.__base_dn,
            '(&(objectCategory=person)(objectClass=user)(userAccountControl:1.2.840.113556.1.4.803:=65536))',
            ('sAMAccountName',),
        )
