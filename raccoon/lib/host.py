import os
from ipaddress import ip_address
from raccoon.lib.dns_handler import DNSHandler
from raccoon.utils.exceptions import HostHandlerException
from raccoon.utils.helper_utils import HelperUtilities
from raccoon.utils.logger import Logger


class Host:
    """
    Host parsing, IP to host resolution (and vice verse), etc
    Sets domain/IP, port, protocol. also tries to parse FQDN, naked domain, if possible.
    """
    def __init__(self, target, dns_records):
        self.target = target.strip()
        self.dns_records = dns_records
        self.port = 80
        self.protocol = "http"
        self.is_ip = False
        self.fqdn = None
        self.naked = None
        self.dns_results = {}
        log_file = HelperUtilities.get_output_path("{}/dns_records.txt".format(self.target))
        self._create_host_dir(log_file)
        self.logger = Logger(log_file)

    def __str__(self):
        return "Host [{}]".format(self.target)

    def __repr__(self):
        return self.__dict__

    @staticmethod
    def _create_host_dir(path):
        try:
            os.mkdir("/".join(path.split("/")[:-1]))
        except FileExistsError:
            pass

    def validate_ip(self, addr=None):
        if not addr:
            addr = self.target
        try:
            ip_address(addr.strip())
            return True
        except ValueError:
            return

    def _extract_port(self, addr):
        try:
            self.target, self.port = addr.split(":")
            self.port = int(self.port)
            self.logger.info("Port detected: {}".format(self.port))
        except IndexError:
            self.logger.info("Did not detect port. Using default port 80")
            return
        return

    def _is_proto(self, domain=None):
        if not domain:
            domain = self.target
        if "://" in domain:
            if any(domain.startswith(proto) for proto in ("https", "http")):
                return True
            else:
                raise HostHandlerException("Unknown or unsupported protocol: {}".format(self.target.split("://")[0]))
        return

    def write_up(self):
        self.logger.info("Writing {} DNS query results".format(self.target))

        for record in self.dns_results:
            self.logger.debug(record+"\n")
            for value in self.dns_results.get(record):
                self.logger.debug("\t{}".format(value))

    def parse(self):
        """
        Try to extract domain (full, naked, sub-domain), IP and port.
        """
        if self.target.endswith("/"):
            self.target = self.target[:-1]

        if self._is_proto(self.target):
            try:
                self.protocol, self.target = self.target.split("://")
                self.logger.info("Protocol detected: {}".format(self.protocol))
                if self.protocol.lower() == "https" and self.port == 80:
                    self.port = 443
            except ValueError:
                raise HostHandlerException("Could not make domain and protocol from host")

        if ":" in self.target:
            self._extract_port(self.target)

        if self.validate_ip(self.target):
            self.logger.info("Detected {} as an IP address.".format(self.target))
            self.is_ip = True
            return

        domains = []
        if self.target.startswith("www."):
            # Obviously an FQDN
            domains.extend((self.target, self.target.split("www.")[1]))
            self.fqdn = self.target
            self.naked = ".".join(self.fqdn.split('.')[1:])
        else:
            # Can't be sure if FQDN or just naked domain
            domains.append(self.target)

        self.dns_results = DNSHandler.query_dns(domains, self.dns_records)

        if self.dns_results.get("CNAME"):
            # Naked domains shouldn't hold CNAME records according to RFC regulations
            self.logger.info("Found {} to be an FQDN by present CNAME record ".format(self.target))
            self.fqdn = self.target
            self.naked = ".".join(self.fqdn.split('.')[1:])

        self.write_up()
