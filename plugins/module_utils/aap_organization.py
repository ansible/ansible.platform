from ..module_utils.aap_object import AAPObject
import json
from urllib.parse import urlencode
from ansible.module_utils.urls import open_url

__metaclass__ = type


class AAPOrganization(AAPObject):
    API_ENDPOINT_NAME = "organizations"
    ITEM_TYPE = "organization"

    def unique_field(self):
        return self.module.IDENTITY_FIELDS["organizations"]

    def set_new_fields(self):
        self.set_name_field()

        description = self.params.get("description")
        if description is not None:
            self.new_fields["description"] = description

        users = self.params.get("users")
        if users is not None:
            self.new_fields["users"] = users

        admins = self.params.get("admins")
        if admins is not None:
            self.new_fields["admins"] = admins

    def post_ensure(self):
        """
        Called after ensure/create/update when state is present/enforced.
        Reconciles Controller-only relations:
          - default_environment
          - galaxy_credentials (many-to-many)
        Returns True if anything changed.
        """
        org_id = getattr(self, "item_id", None)
        if not org_id:
            return False

        state = self.params.get("state", "present")
        if state not in ("present", "enforced"):
            return False

        changed = False
        check_mode = self.module.check_mode

        base = self._controller_base()

        desired_ee = self.params.get("default_environment", None)
        if desired_ee is not None:
            ee_id = self._resolve_id(
                endpoint=f"{base}/execution_environments/",
                value=desired_ee,
                name_field="name",
            )

            if ee_id is None:
                self.module.warn(
                    f"Organization default_environment '{desired_ee}' could not be resolved "
                    f"to an Execution Environment id; skipping EE update."
                )
            else:
                current = self._http_get(f"{base}/organizations/{org_id}/")
                current_ee = current.get("default_environment")
                if current_ee != ee_id:
                    changed = True
                    if not check_mode:
                        self._http_patch(
                            f"{base}/organizations/{org_id}/",
                            {"default_environment": ee_id},
                        )

        desired_gc = self.params.get("galaxy_credentials", None)
        if desired_gc is not None:
            desired_ids = set()
            for cred in desired_gc:
                cid = self._resolve_id(
                    endpoint=f"{base}/credentials/",
                    value=cred,
                    name_field="name",
                )
                if cid is None:
                    self.module.warn(
                        f"Galaxy credential '{cred}' could not be resolved; skipping."
                    )
                else:
                    desired_ids.add(cid)

            current = self._http_get(
                f"{base}/organizations/{org_id}/galaxy_credentials/"
            )
            current_list = current.get("results", current or [])
            current_ids = {c["id"] for c in current_list}

            to_add = desired_ids - current_ids
            to_del = current_ids - desired_ids

            if to_add or to_del:
                changed = True
                if not check_mode:
                    for cid in sorted(to_add):
                        self._http_post(
                            f"{base}/organizations/{org_id}/galaxy_credentials/",
                            {"id": cid},
                            expect_status=(201, 204),
                        )
                    for cid in sorted(to_del):
                        self._http_delete(
                            f"{base}/organizations/{org_id}/galaxy_credentials/{cid}/",
                            expect_status=(204,),
                        )

        return changed

    def _detect_controller_base(self):
        """
        Find a working Controller v2 base. Try gateway-proxied first,
        fall back to the direct controller path.
        """
        candidates = [
            "/api/gateway/v1/controller/api/v2",
            "/api/controller/v2",
        ]
        for base in candidates:
            try:
                self._open("GET", f"{base}/ping/", data=None, expect_status=(200,))
                return base
            except Exception:
                continue

        self.module.fail_json(
            msg="Could not find Controller API. Tried: "
                + ", ".join(candidates)
        )

    def _controller_base(self):
        if not hasattr(self, "_ctl_base"):
            self._ctl_base = self._detect_controller_base()
        return self._ctl_base

    def _resolve_id(self, endpoint, value, name_field="name"):
        """ """
        if value is None:
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, str) and value.isdigit():
            return int(value)

        if isinstance(value, str) and "/" in value:
            parts = [p for p in value.rstrip("/").split("/") if p]
            if parts and parts[-1].isdigit():
                return int(parts[-1])

        ql = self._http_get(f"{endpoint}?{name_field}={self._quote(value)}")
        items = ql.get("results", ql if isinstance(ql, list) else [])

        for item in items:
            if str(item.get(name_field)) == str(value):
                return int(item["id"])

        if len(items) == 1 and "id" in items[0]:
            return int(items[0]["id"])

        return None

    def _gw_base(self):
        host = self.module.params.get("aap_hostname") or self.module.params.get("gateway_hostname") or ""
        return host.rstrip("/")

    def _open(self, method, path, data=None, headers=None, expect_status=(200,)):
        url = f"{self._gw_base()}{path}"
        print(url)
        hdrs = {"Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)

        body = None
        if data is not None:
            body = json.dumps(data)

        resp = open_url(
            url=url,
            method=method,
            data=body,
            headers=hdrs,
            validate_certs=self.module.params.get("aap_validate_certs", True),
            url_username=self.module.params.get("aap_username"),
            url_password=self.module.params.get("aap_password"),
            force_basic_auth=True,
            timeout=30,
        )
        if hasattr(resp, "code") and expect_status and resp.code not in expect_status:
            self.module.fail_json(msg=f"HTTP {method} {url} -> unexpected {resp.code}")

        raw = resp.read()
        try:
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    def _http_get(self, path):
        return self._open("GET", path, data=None, expect_status=(200,))

    def _http_post(self, path, payload, expect_status=(201,)):
        return self._open("POST", path, data=payload, expect_status=expect_status)

    def _http_patch(self, path, payload, expect_status=(200,)):
        return self._open("PATCH", path, data=payload, expect_status=expect_status)

    def _http_delete(self, path, expect_status=(204,)):
        return self._open("DELETE", path, data=None, expect_status=expect_status)
    @staticmethod
    def _quote(s):
        from urllib.parse import quote as _q
        return _q(str(s), safe="")