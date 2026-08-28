from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests
from requests.auth import HTTPBasicAuth

from .config import Settings
from .consolidation import normalize_sku
from .db import Database, utc_now_iso
from .security import TokenCipher

AUTHORIZATION_ENDPOINT = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_ENDPOINT = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
SCOPE = "com.intuit.quickbooks.accounting"


class QBOError(RuntimeError):
    pass


def _unix_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _fault_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip().replace("\n", " ")
        return text[:800] or f"HTTP {response.status_code}"

    errors = payload.get("Fault", {}).get("Error", [])
    if isinstance(errors, dict):
        errors = [errors]
    messages = []
    for error in errors:
        message = error.get("Message") or "Erro do QuickBooks"
        detail = error.get("Detail") or ""
        code = error.get("code") or ""
        combined = " — ".join(part for part in [message, detail] if part)
        if code:
            combined += f" (código {code})"
        messages.append(combined)
    if messages:
        return "; ".join(messages)
    return str(payload)[:1000]


class QuickBooksService:
    def __init__(self, settings: Settings, db: Database, cipher: TokenCipher) -> None:
        self.settings = settings
        self.db = db
        self.cipher = cipher
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "EstoqueConsolidadoQBO/1.0",
            }
        )

    @staticmethod
    def new_state() -> str:
        return secrets.token_urlsafe(32)

    def authorization_url(self, state: str) -> str:
        if not self.settings.credentials_ready:
            raise QBOError("Preencha QBO_CLIENT_ID e QBO_CLIENT_SECRET no arquivo .env.")
        params = {
            "client_id": self.settings.qbo_client_id,
            "response_type": "code",
            "scope": SCOPE,
            "redirect_uri": self.settings.qbo_redirect_uri,
            "state": state,
        }
        return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    def _token_request(self, data: dict[str, str]) -> dict[str, Any]:
        try:
            response = self.session.post(
                TOKEN_ENDPOINT,
                auth=HTTPBasicAuth(
                    self.settings.qbo_client_id, self.settings.qbo_client_secret
                ),
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise QBOError(f"Falha de rede ao solicitar token do QuickBooks: {exc}") from exc

        if not response.ok:
            raise QBOError(
                f"QuickBooks recusou o token (HTTP {response.status_code}): "
                f"{_fault_message(response)}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise QBOError("A resposta de token do QuickBooks não era JSON válido.") from exc

    def exchange_code(self, code: str) -> dict[str, Any]:
        return self._token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.settings.qbo_redirect_uri,
            }
        )

    def save_authorization(self, slot: str, realm_id: str, token_data: dict[str, Any]) -> None:
        now = _unix_now()
        access_expires_at = now + int(token_data.get("expires_in", 3600))
        refresh_expires_at = now + int(
            token_data.get("x_refresh_token_expires_in", 8_726_400)
        )
        access_token = str(token_data["access_token"])
        refresh_token = str(token_data["refresh_token"])
        company_name = self.fetch_company_name(realm_id, access_token)
        self.db.save_connection(
            slot=slot,
            realm_id=realm_id,
            company_name=company_name,
            access_token=self.cipher.encrypt(access_token),
            refresh_token=self.cipher.encrypt(refresh_token),
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
            is_demo=False,
        )

    def _api_params(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if self.settings.qbo_minor_version:
            params["minorversion"] = self.settings.qbo_minor_version
        if extra:
            params.update(extra)
        return params

    def fetch_company_name(self, realm_id: str, access_token: str) -> str:
        url = (
            f"{self.settings.api_base_url}/v3/company/{realm_id}/"
            f"companyinfo/{realm_id}"
        )
        try:
            response = self.session.get(
                url,
                params=self._api_params(),
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )
            if response.ok:
                payload = response.json()
                info = payload.get("CompanyInfo", {})
                return (
                    info.get("CompanyName")
                    or info.get("LegalName")
                    or f"QuickBooks {realm_id}"
                )
        except (requests.RequestException, ValueError):
            pass
        return f"QuickBooks {realm_id}"

    def _refresh(self, slot: str, connection: dict) -> tuple[str, dict]:
        refresh_token = self.cipher.decrypt(connection.get("refresh_token"))
        if not refresh_token:
            raise QBOError(f"A conexão {slot} não possui refresh token.")

        token_data = self._token_request(
            {"grant_type": "refresh_token", "refresh_token": refresh_token}
        )
        now = _unix_now()
        encrypted_access = self.cipher.encrypt(str(token_data["access_token"]))
        encrypted_refresh = self.cipher.encrypt(str(token_data["refresh_token"]))
        access_expires_at = now + int(token_data.get("expires_in", 3600))
        refresh_expires_at = now + int(
            token_data.get(
                "x_refresh_token_expires_in",
                max(0, int(connection.get("refresh_expires_at") or now) - now),
            )
        )
        self.db.update_tokens(
            slot,
            access_token=encrypted_access or "",
            refresh_token=encrypted_refresh or "",
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
        )
        updated = self.db.get_connection(slot)
        if not updated:
            raise QBOError("A conexão desapareceu durante a renovação do token.")
        return str(token_data["access_token"]), updated

    def _access_token(self, slot: str, *, force_refresh: bool = False) -> tuple[str, dict]:
        connection = self.db.get_connection(slot)
        if not connection:
            raise QBOError(f"{self.settings.labels[slot]} ainda não está conectada.")
        if connection.get("is_demo"):
            raise QBOError("Dados de demonstração não podem ser sincronizados com o QuickBooks.")

        expires_at = int(connection.get("access_expires_at") or 0)
        if force_refresh or expires_at <= _unix_now() + 120:
            return self._refresh(slot, connection)

        token = self.cipher.decrypt(connection.get("access_token"))
        if not token:
            return self._refresh(slot, connection)
        return token, connection

    def _get(
        self,
        slot: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> dict[str, Any]:
        access_token, _ = self._access_token(slot)
        try:
            response = self.session.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=45,
            )
        except requests.RequestException as exc:
            raise QBOError(f"Falha de rede ao consultar o QuickBooks: {exc}") from exc

        if response.status_code == 401 and retry_auth:
            access_token, _ = self._access_token(slot, force_refresh=True)
            response = self.session.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=45,
            )

        if response.status_code == 429:
            retry_after = min(int(response.headers.get("Retry-After", "2") or 2), 10)
            time.sleep(max(retry_after, 1))
            return self._get(slot, url, params=params, retry_auth=False)

        if not response.ok:
            raise QBOError(
                f"Consulta ao QuickBooks falhou (HTTP {response.status_code}): "
                f"{_fault_message(response)}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise QBOError("O QuickBooks retornou uma resposta que não era JSON válido.") from exc

    def fetch_inventory(self, slot: str) -> list[dict]:
        slot = slot.upper()
        connection = self.db.get_connection(slot)
        if not connection:
            raise QBOError(f"{self.settings.labels[slot]} ainda não está conectada.")
        realm_id = connection["realm_id"]
        url = f"{self.settings.api_base_url}/v3/company/{realm_id}/query"

        all_items: list[dict] = []
        start_position = 1
        max_results = 1000

        while True:
            query = (
                "SELECT * FROM Item "
                f"STARTPOSITION {start_position} MAXRESULTS {max_results}"
            )
            payload = self._get(
                slot,
                url,
                params=self._api_params({"query": query}),
            )
            items = payload.get("QueryResponse", {}).get("Item", [])
            if isinstance(items, dict):
                items = [items]
            if not items:
                break

            for item in items:
                item_type = str(item.get("Type") or "")
                track_qty = bool(item.get("TrackQtyOnHand")) or item_type.lower() == "inventory"
                if not track_qty:
                    continue
                name = (
                    item.get("FullyQualifiedName")
                    or item.get("Name")
                    or f"Item {item.get('Id', '')}"
                )
                sku = str(item.get("Sku") or "").strip()
                normalized_sku, _ = normalize_sku(sku, str(name))
                try:
                    qty = float(item.get("QtyOnHand") or 0)
                except (TypeError, ValueError):
                    qty = 0.0
                all_items.append(
                    {
                        "item_id": str(item.get("Id") or f"sem-id-{len(all_items)}"),
                        "sku": sku,
                        "normalized_sku": normalized_sku,
                        "name": str(name),
                        "qty_on_hand": qty,
                        "item_type": item_type,
                        "track_qty_on_hand": track_qty,
                        "active": bool(item.get("Active", True)),
                    }
                )

            if len(items) < max_results:
                break
            start_position += max_results

        return all_items

    def sync_inventory(self, slot: str) -> int:
        started_at = utc_now_iso()
        try:
            items = self.fetch_inventory(slot)
            count = self.db.replace_inventory(slot, items)
            self.db.record_sync(
                slot=slot,
                started_at=started_at,
                success=True,
                item_count=count,
                message="Sincronização concluída.",
            )
            return count
        except Exception as exc:
            self.db.record_sync(
                slot=slot,
                started_at=started_at,
                success=False,
                item_count=None,
                message=str(exc),
            )
            raise
