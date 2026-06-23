from __future__ import annotations

import re
import unicodedata
from pathlib import PurePosixPath
from typing import Optional

import requests


class StorageError(Exception):
    """Erro generico de operacao no Supabase Storage."""


class StorageService:
    """Cliente minimo para a API REST do Supabase Storage (self-hosted).

    Usa a service role key (acesso admin) para subir arquivos em bucket privado
    e gerar URLs assinadas temporarias para entrega ao usuario.
    """

    def __init__(self, base_url: str, service_key: str, bucket: str, timeout: int = 30):
        if not base_url or not service_key:
            raise StorageError("SUPABASE_URL e SERVICE_ROLE_KEY sao obrigatorios para o Storage.")
        self.base_url = base_url.rstrip("/")
        self.service_key = service_key
        self.bucket = bucket
        self.timeout = timeout

    # ------------------------------------------------------------------ utils
    @property
    def _storage_root(self) -> str:
        return f"{self.base_url}/storage/v1"

    def _headers(self, extra: Optional[dict] = None) -> dict:
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
        }
        if extra:
            headers.update(extra)
        return headers

    @staticmethod
    def sanitize_object_name(filename: str) -> str:
        """Normaliza o nome do arquivo para uma chave segura no bucket.

        Remove acentos, espacos e caracteres problematicos, preservando a extensao.
        Ex.: 'Manual do Coordenador (1).pdf' -> 'Manual_do_Coordenador_1.pdf'
        """
        name = PurePosixPath(filename).name  # descarta qualquer caminho
        nfkd = unicodedata.normalize("NFKD", name)
        ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
        ascii_name = ascii_name.replace(" ", "_")
        ascii_name = re.sub(r"[^A-Za-z0-9._-]", "", ascii_name)
        ascii_name = re.sub(r"_+", "_", ascii_name).strip("._") or "documento"
        return ascii_name

    # --------------------------------------------------------------- operacoes
    def ensure_bucket(self, public: bool = False) -> None:
        """Garante que o bucket exista (idempotente). Cria como PRIVADO por padrao
        (entrega so via URL assinada). No-op se ja existir."""
        get = requests.get(f"{self._storage_root}/bucket/{self.bucket}",
                           headers=self._headers(), timeout=self.timeout)
        if get.status_code == 200:
            return
        resp = requests.post(
            f"{self._storage_root}/bucket",
            json={"name": self.bucket, "id": self.bucket, "public": public},
            headers=self._headers({"Content-Type": "application/json"}),
            timeout=self.timeout,
        )
        # 409 (ou "already exists") cobre corrida entre processos: tratamos como sucesso.
        if resp.status_code == 409 or (resp.status_code >= 400 and "already exist" in resp.text.lower()):
            return
        if resp.status_code >= 400:
            raise StorageError(f"Falha ao criar bucket '{self.bucket}' ({resp.status_code}): {resp.text}")

    def upload(self, object_name: str, content: bytes, content_type: str = "application/octet-stream",
               upsert: bool = True) -> str:
        """Sobe os bytes para o bucket. Retorna o nome do objeto armazenado."""
        url = f"{self._storage_root}/object/{self.bucket}/{object_name}"
        headers = self._headers({
            "Content-Type": content_type,
            "x-upsert": "true" if upsert else "false",
        })
        resp = requests.post(url, data=content, headers=headers, timeout=self.timeout)
        if resp.status_code >= 400:
            raise StorageError(f"Falha no upload ({resp.status_code}): {resp.text}")
        return object_name

    def create_signed_url(self, object_name: str, expires_in: int = 3600) -> str:
        """Gera uma URL assinada absoluta para download temporario do objeto."""
        url = f"{self._storage_root}/object/sign/{self.bucket}/{object_name}"
        resp = requests.post(url, json={"expiresIn": expires_in},
                             headers=self._headers({"Content-Type": "application/json"}),
                             timeout=self.timeout)
        if resp.status_code >= 400:
            raise StorageError(f"Falha ao gerar signed URL ({resp.status_code}): {resp.text}")
        signed = resp.json().get("signedURL") or resp.json().get("signedUrl")
        if not signed:
            raise StorageError(f"Resposta sem signedURL: {resp.text}")
        # A API retorna um caminho relativo (ex.: /object/sign/...); montamos a URL absoluta.
        if signed.startswith("http"):
            return signed
        return f"{self._storage_root}{signed if signed.startswith('/') else '/' + signed}"

    def list_objects(self, prefix: str = "", limit: int = 100) -> list[dict]:
        """Lista objetos do bucket (opcionalmente por prefixo)."""
        url = f"{self._storage_root}/object/list/{self.bucket}"
        body = {"prefix": prefix, "limit": limit, "offset": 0,
                "sortBy": {"column": "name", "order": "asc"}}
        resp = requests.post(url, json=body,
                             headers=self._headers({"Content-Type": "application/json"}),
                             timeout=self.timeout)
        if resp.status_code >= 400:
            raise StorageError(f"Falha ao listar objetos ({resp.status_code}): {resp.text}")
        return resp.json()

    def exists(self, object_name: str) -> bool:
        """Verifica se um objeto existe no bucket pelo nome exato.

        Usa o campo `search` do list (a API trata `prefix` como pasta, entao um nome
        completo em `prefix` nao casa; `search` filtra pelo nome dentro do prefixo).
        """
        url = f"{self._storage_root}/object/list/{self.bucket}"
        body = {"prefix": "", "search": object_name, "limit": 100, "offset": 0}
        resp = requests.post(url, json=body,
                             headers=self._headers({"Content-Type": "application/json"}),
                             timeout=self.timeout)
        if resp.status_code >= 400:
            raise StorageError(f"Falha ao verificar objeto ({resp.status_code}): {resp.text}")
        return any(obj.get("name") == object_name for obj in resp.json())

    @staticmethod
    def _name_tokens(name: str) -> list[str]:
        """Tokens normalizados de um nome de arquivo (sem extensao/acentos), para
        comparacao frouxa. Ex.: 'Manual do Coordenador.pdf' -> ['manual','do','coordenador']."""
        stem = PurePosixPath(name).stem
        ascii_stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
        return [t for t in re.split(r"[^a-z0-9]+", ascii_stem.lower()) if t]

    @classmethod
    def _name_similarity(cls, a: str, b: str) -> float:
        """Similaridade [0,1] entre dois nomes por sobreposicao de tokens, tolerante
        a singular/plural e variacoes (casa por prefixo de >=4 chars, ex.: 'coordenador'
        ~ 'coordenadores', 'do' ~ 'dos'). Base = tokens do nome citado (a)."""
        ta, tb = cls._name_tokens(a), cls._name_tokens(b)
        if not ta or not tb:
            return 0.0
        def hit(t: str) -> bool:
            return any(t == u or (min(len(t), len(u)) >= 4 and (t.startswith(u) or u.startswith(t))) for u in tb)
        return sum(1 for t in ta if hit(t)) / len(ta)

    def resolve_object_name(self, name: str) -> Optional[str]:
        """Resolve o nome real do objeto no bucket a partir de um nome citado.

        Ordem: (1) nome sanitizado (padrao dos uploads pela rota do app); (2) nome
        cru/basename (uploads pelo dashboard, com espacos/acentos); (3) fallback
        frouxo contra a LISTAGEM real do bucket — resolve o descasamento entre o nome
        que o LightRAG cita ('Manual do Coordenador.pdf') e o objeto armazenado
        ('Manual_dos_Coordenadores.pdf'). Retorna o nome no bucket, ou None.
        """
        candidates: list[str] = []
        for cand in (self.sanitize_object_name(name), PurePosixPath(name).name):
            if cand and cand not in candidates:
                candidates.append(cand)
        for cand in candidates:
            if self.exists(cand):
                return cand

        # Fallback frouxo: confronta com os objetos REAIS do bucket.
        try:
            objects = [o.get("name", "") for o in self.list_objects(limit=100) if o.get("name")]
        except StorageError:
            objects = []
        if not objects:
            return None
        # ponytail: com um unico manual (caso atual), o objeto e ele; senao, melhor
        # match por sobreposicao de tokens (>=0.5). Subir para indice/embeddings se um
        # dia houver muitos documentos com nomes ambiguos.
        if len(objects) == 1:
            return objects[0]
        best, best_score = None, 0.0
        for obj in objects:
            score = self._name_similarity(name, obj)
            if score > best_score:
                best, best_score = obj, score
        return best if best_score >= 0.5 else None

    def delete(self, object_name: str) -> None:
        """Remove um objeto do bucket."""
        url = f"{self._storage_root}/object/{self.bucket}/{object_name}"
        resp = requests.delete(url, headers=self._headers(), timeout=self.timeout)
        if resp.status_code >= 400:
            raise StorageError(f"Falha ao remover objeto ({resp.status_code}): {resp.text}")

    def download(self, object_name: str) -> bytes:
        """Baixa os bytes de um objeto do bucket (acesso admin via service key).

        Usado pela sidebar de fontes para extrair o texto da pagina citada do PDF.
        """
        url = f"{self._storage_root}/object/{self.bucket}/{object_name}"
        resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
        if resp.status_code >= 400:
            raise StorageError(f"Falha ao baixar objeto ({resp.status_code}): {resp.text}")
        return resp.content
