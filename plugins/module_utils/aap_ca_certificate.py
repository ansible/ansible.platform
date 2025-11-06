# coding: utf-8 -*-
# Copyright: (c) 2025, Hui Song <hsong@redhat.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import hashlib
from datetime import datetime, timezone

from ..module_utils.aap_object import AAPObject

try:
    from cryptography import x509
    from cryptography.exceptions import UnsupportedAlgorithm

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


class AAPCACertificate(AAPObject):
    API_ENDPOINT_NAME = "ca_certificates"
    ITEM_TYPE = "ca_certificate"

    def __init__(self, module):
        super(AAPCACertificate, self).__init__(module)
        self._validate_dependencies()

    def unique_field(self):
        return self.module.IDENTITY_FIELDS["ca_certificates"]

    def _validate_dependencies(self):
        """Validate that required dependencies are available."""
        if not HAS_CRYPTOGRAPHY:
            self.module.fail_json(
                msg="The cryptography library is required for CA certificate validation. "
                "Install it with: pip install cryptography"
            )

    def _validate_pem_data(self, pem_data):
        """Validate PEM certificate data and check expiry."""
        try:
            # load_pem_x509_certificates expects bytes
            certificates = x509.load_pem_x509_certificates(pem_data.encode("utf-8"))
        except (ValueError, UnsupportedAlgorithm) as e:
            self.module.fail_json(msg=f"Invalid PEM certificate data: {e}")

        if not certificates:
            self.module.fail_json(msg="No valid certificates found in PEM data")

        # Check expiry of each certificate in the chain
        now = datetime.now(timezone.utc)
        for certificate in certificates:
            if now > certificate.not_valid_after_utc:
                self.module.fail_json(
                    msg=f"Certificate has expired: {certificate.not_valid_after_utc}"
                )

    def _validate_sha256(self, pem_data, sha256):
        """Validate that the provided SHA256 matches the PEM data."""
        if sha256:
            # Normalize PEM data for consistent hashing
            normalized_pem = pem_data.strip().replace("\r\n", "\n").replace("\r", "\n")
            calculated_sha256 = hashlib.sha256(
                normalized_pem.encode("utf-8")
            ).hexdigest()
            if calculated_sha256 != sha256:
                self.module.fail_json(
                    msg=f"SHA256 mismatch. Expected: {sha256}, Calculated: {calculated_sha256}"
                )

    def set_new_fields(self):
        """Set the fields for create/update operations."""
        pem_data = self.module.params.get("pem_data")
        sha256 = self.module.params.get("sha256")

        # Validate PEM data and SHA256 if provided
        if pem_data and sha256:
            self._validate_pem_data(pem_data)
            self._validate_sha256(pem_data, sha256)

        # Set the fields for API request
        name = self.module.params.get("name")
        if name is not None:
            self.new_fields["name"] = name

        if pem_data is not None:
            self.new_fields["pem_data"] = pem_data

        if sha256 is not None:
            self.new_fields["sha256"] = sha256

        related_id_reference = self.module.params.get("related_id_reference")
        if related_id_reference is not None:
            self.new_fields["related_id_reference"] = related_id_reference

    def get_existing_item(self):
        """Override to add URL field for deletion."""
        item = super().get_existing_item()
        if item:
            # Always set the correct URL for deletion
            item["url"] = f"{self.API_ENDPOINT_NAME}/{item['id']}"
            self.module.debug(f"CA certificate item ID: {item.get('id')}")
            self.module.debug(f"Set URL to: {item['url']}")
        return item
