"""Opt-in B interface candidate; no HTTP registration or shared contract change.

A constructs these objects in its trusted process and supplies real transport
metadata to the user surface. Workers receive a scoped CollaborationAPI. This
is a call capability boundary, not isolation from same-account arbitrary code.
Facade reference/grant bindings live only in memory. V1 private SQLite intents
retain their original response for internal retry; a restart never restores authority
from an actor name, review ID or the persisted publication journal.
"""
from __future__ import annotations

import copy
import hashlib
import secrets
import threading
import time

from .errors import WorkspaceError, require
from .git_publication import GitPublisher
from .proposals import API_VERSION, validate_context
from .schema import canonical, fields, identifier, MAP_REV
from .storage import Store


CONTEXT_FIELDS = ("workspaceId", "mapId", "mode", "codeRepoId", "codeRevision",
                  "baseMapRevision", "draftId", "draftRevision")
VERSION_FIELDS = ("codeRepoId", "mapId", "codeRevision", "mapRevision",
                  "mapSourceRevision", "verifiedCodeRevision")


def workspace_context(workspace, draft=None):
    if draft is not None:
        return {key: copy.deepcopy(draft[key]) for key in CONTEXT_FIELDS}
    return {**{key: workspace[key] for key in CONTEXT_FIELDS[:5]},
            "baseMapRevision": workspace["mapRevision"], "draftId": None,
            "draftRevision": None}


def version_reference(envelope):
    if envelope is None:
        return None
    return {**{key: envelope["version"][key] for key in VERSION_FIELDS
               if key != "mapSourceRevision"},
            "mapSourceRevision": envelope["provenance"]["mapSourceRevision"]}


def _request(request, required=(), optional=()):
    fields(request, ("apiVersion", "requestId") + required, optional)
    require(request["apiVersion"] == API_VERSION)
    identifier(request["requestId"])


def _success(request, context, data, status="ok"):
    return {"apiVersion": API_VERSION, "requestId": request["requestId"],
            "status": status, "context": context, "data": copy.deepcopy(data)}


def _error(request, exc, context=None):
    request_id = request.get("requestId") if isinstance(request, dict) else None
    result = {"apiVersion": API_VERSION, "requestId": request_id
              if isinstance(request_id, str) and len(request_id) <= 120 else None,
              **exc.as_dict()}
    if context is not None:
        result["currentContext"] = context
    return result


class _ScopedSurface:
    def __init__(self, service, workspace_id):
        self._service = service
        self._workspace_id = identifier(workspace_id)
        self._map_id = self._workspace()["mapId"]

    def _workspace(self):
        with self._service.store.transaction() as db:
            ws = Store.get(db, "workspace", self._workspace_id)
        if hasattr(self, "_map_id"):
            require(ws["mapId"] == self._map_id, "STALE_CONTEXT")
        return ws

    def _draft(self, draft_id):
        draft = self._service.get_draft(identifier(draft_id))
        require(draft["workspaceId"] == self._workspace_id and draft["mapId"] == self._map_id,
                "REQUEST_FORBIDDEN")
        return draft

    def _expect(self, context, *, needs_draft=False):
        validate_context(context)
        require(context["workspaceId"] == self._workspace_id
                and context["mapId"] == self._map_id, "REQUEST_FORBIDDEN")
        ws = self._workspace()
        draft = self._draft(context["draftId"]) if context["draftId"] is not None else None
        require(not needs_draft or draft is not None)
        if draft is not None:
            require(all(draft[k] == ws[k] for k in CONTEXT_FIELDS[:5]), "STALE_CONTEXT")
        actual = workspace_context(ws, draft)
        require(all(actual[k] == context[k] for k in
                    ("workspaceId", "mapId", "mode", "codeRepoId", "codeRevision", "draftId")),
                "STALE_CONTEXT")
        require(actual["baseMapRevision"] == context["baseMapRevision"]
                and actual["draftRevision"] == context["draftRevision"], "REVISION_CONFLICT")
        return ws, draft

    def _current_context(self, request):
        # Only invoked after scope/auth checks. Never echo a foreign draft.
        ws = self._workspace()
        context = request.get("context", {}) if isinstance(request, dict) else {}
        draft_id = context.get("draftId") if isinstance(context, dict) else None
        draft = None
        if isinstance(draft_id, str):
            try:
                candidate = self._draft(draft_id)
                if (all(candidate[k] == ws[k] for k in CONTEXT_FIELDS[:5])
                        and candidate["baseMapRevision"] == ws["mapRevision"]):
                    draft = candidate
            except WorkspaceError:
                pass
        return workspace_context(ws, draft)

    def _exact(self, reference):
        fields(reference, VERSION_FIELDS)
        require(reference["mapId"] == self._map_id, "REQUEST_FORBIDDEN")
        revision = reference["mapRevision"]
        require(isinstance(revision, str) and MAP_REV.fullmatch(revision))
        envelope = self._service.get_version(self._workspace_id, revision)
        require(version_reference(envelope) == reference, "STALE_CONTEXT")
        return envelope


class UserWorkspaceAPI(_ScopedSurface):
    """A-owned trusted adapter invokes call(action, JSON request, auth=metadata).

    The server opens the initial workspace with WorkspaceService, then creates
    this per-workspace surface. JSON cannot select another workspace or supply
    an actor, confirmationToken or publicationToken. Session creation remains
    the trusted gateway's responsibility, outside worker/browser JSON dispatch.
    """
    ACTIONS = {
        "openWorkspace": "_open", "readView": "_read", "prepareDraft": "_prepare",
        "previewSelection": "_preview_selection",
        "saveDraft": "_save", "restoreAsDraft": "_restore", "associateCode": "_associate",
        "previewReview": "_preview", "confirmReview": "_confirm",
        "publishVersion": "_publish", "publicationStatus": "_status",
        "importExactVersion": "_import",
    }

    def __init__(self, service, gateway, workspace_id, *, source_registration_id=None):
        require(gateway.service is service, "INVALID_INPUT")
        super().__init__(service, workspace_id)
        self._gateway = gateway
        self._previews = {}
        self._reviews = {}
        self._lock = threading.RLock()
        self._source_registration_id = (identifier(source_registration_id)
                                        if source_registration_id is not None else None)

    def _prune(self):
        now = time.time()
        self._previews = {key: item for key, item in self._previews.items()
                          if item["expiresAt"] > now}
        self._reviews = {key: item for key, item in self._reviews.items()
                         if item["expiresAt"] > now}

    def _authorize(self, auth):
        require(isinstance(auth, dict) and set(auth) ==
                {"peer", "host", "origin", "session_id", "csrf_token"}, "REQUEST_FORBIDDEN")
        self._gateway._session(**auth)
        return hashlib.sha256(auth["session_id"].encode()).hexdigest()

    def call(self, action, request, *, auth):
        authorized = False
        try:
            auth = copy.deepcopy(auth)
            binding = self._authorize(auth)
            authorized = True
            require(isinstance(action, str) and action in self.ACTIONS, "REQUEST_FORBIDDEN")
            canonical(request)
            request = copy.deepcopy(request)
            # All reads and writes have identical transport/session protection.
            with self._lock:
                self._prune()
                return getattr(self, self.ACTIONS[action])(request, auth, binding)
        except (TypeError, KeyError, IndexError, AttributeError, RecursionError, OverflowError):
            return _error(request, WorkspaceError("INVALID_INPUT"))
        except WorkspaceError as exc:
            current = None
            if authorized and exc.code in ("REVISION_CONFLICT", "STALE_CONTEXT"):
                try:
                    current = self._current_context(request)
                except WorkspaceError:
                    pass
            return _error(request, exc, current)

    def _view(self, request, draft=None):
        snapshot = self._service.graph_snapshot(self._workspace_id)
        ws = snapshot["workspace"]
        data = {"workspaceContext": workspace_context(ws),
                "currentVersionRef": version_reference(snapshot["versionEnvelope"]),
                "versionEnvelope": snapshot["versionEnvelope"], "draft": draft,
                **{key: snapshot[key] for key in ("pendingNodeIds", "pendingEvidenceIds",
                   "pendingProcessIds", "applicability", "limits")}}
        if draft is not None:
            current = (all(ws[key] == draft[key] for key in CONTEXT_FIELDS[:5])
                       and draft["baseMapRevision"] == ws["mapRevision"])
            data.update(draftStatus=draft["status"],
                        contextCurrent=current,
                        canEditThisDraft=current and draft["status"] not in ("publishing", "published"),
                        reviewRequired=draft["status"] not in ("review_approved", "publishing", "published"))
        return _success(request, workspace_context(ws, draft), data,
                        draft["status"] if draft else "workspace")

    def _open(self, request, auth, binding):
        _request(request, ("context",), ("targetCodeRevision",))
        ws, _ = self._expect(request["context"])
        require(request["context"]["draftId"] is None)
        if "targetCodeRevision" in request:
            self._service.open_workspace(workspace_id=self._workspace_id,
                    code_revision=request["targetCodeRevision"], expected_context=request["context"])
        return self._view(request)

    def _read(self, request, auth, binding):
        _request(request, optional=("draftId",))
        draft = self._draft(request["draftId"]) if "draftId" in request else None
        return self._view(request, draft)

    def _prepare(self, request, auth, binding):
        _request(request, ("context", "graph", "origin"), ("proposal", "selectedCandidateId"))
        ws, _ = self._expect(request["context"])
        require(request["context"]["draftId"] is None)
        if "proposal" in request:
            require("selectedCandidateId" in request)
            draft = self._service.create_candidate_draft(self._workspace_id,
                    proposal=request["proposal"], selected_candidate_id=request["selectedCandidateId"],
                    graph=request["graph"], base_map_revision=ws["mapRevision"], origin=request["origin"],
                    expected_context=request["context"])
        else:
            require("selectedCandidateId" not in request and request["origin"] == "manual")
            draft = self._service.create_draft(self._workspace_id, graph=request["graph"],
                        base_map_revision=ws["mapRevision"], origin=request["origin"],
                        expected_context=request["context"])
        return self._view(request, draft)

    def _save(self, request, auth, binding):
        _request(request, ("context", "operations"), ("proposal", "selection"))
        _, draft = self._expect(request["context"], needs_draft=True)
        args = {"operations": request["operations"],
                "expected_draft_revision": request["context"]["draftRevision"],
                "base_map_revision": request["context"]["baseMapRevision"]}
        if "proposal" in request:
            require("selection" in request)
            draft = self._service.apply_candidate_selection(draft["draftId"],
                         proposal=request["proposal"], selection=request["selection"], **args)
        else:
            require("selection" not in request and isinstance(request["operations"], list))
            # Manual editing must not impersonate a generated candidate.
            require(all(isinstance(op, dict) and op.get("source", "human") == "human"
                        for op in request["operations"]))
            draft = self._service.apply_draft_operations(draft["draftId"],
                                  proposal_id=draft["proposalId"], **args)
        return self._view(request, draft)

    def _preview_selection(self, request, auth, binding):
        _request(request, ("context", "proposal", "selection", "operations"))
        self._expect(request["context"], needs_draft=True)
        result = self._service.preview_candidate_selection(request["context"]["draftId"],
                    proposal=request["proposal"], selection=request["selection"],
                    operations=request["operations"], expected_context=request["context"])
        return _success(request, result["context"], result, "selection_preview")

    def _restore(self, request, auth, binding):
        _request(request, ("context", "mapRevision"))
        ws, _ = self._expect(request["context"])
        require(request["context"]["draftId"] is None)
        draft = self._service.create_draft(self._workspace_id,
                    base_map_revision=ws["mapRevision"], from_map_revision=request["mapRevision"],
                    expected_context=request["context"])
        return self._view(request, draft)

    def _associate(self, request, auth, binding):
        _request(request, ("context", "codeRepoId", "codeRevision"))
        ws, _ = self._expect(request["context"])
        require(request["context"]["draftId"] is None)
        self._service.associate_code(self._workspace_id, code_repo_id=request["codeRepoId"],
                    code_revision=request["codeRevision"], expected_map_revision=ws["mapRevision"])
        return self._view(request)

    @staticmethod
    def _review_args(context, draft):
        return {"expected_draft_revision": context["draftRevision"],
                "expected_map_revision": context["baseMapRevision"],
                "proposal_id": draft["proposalId"], "code_repo_id": context["codeRepoId"],
                "code_revision": context["codeRevision"]}

    def _preview(self, request, auth, binding):
        _request(request, ("context", "reason", "coverage", "limits", "verifyCode"))
        ws, draft = self._expect(request["context"], needs_draft=True)
        require(len(self._previews) < 128, detail="待审预览数量已达上限，请等待过期或继续已有审阅")
        rejected = [copy.deepcopy(item) for entry in draft.get("candidateSelections", [])
                    for item in entry["rejectedCandidates"]]
        result = self._gateway.preview_review(draft["draftId"], auth=auth,
                  **self._review_args(request["context"], draft), reason=request["reason"],
                  coverage=request["coverage"], limits=request["limits"],
                  verify_code=request["verifyCode"], rejected_candidates=rejected)
        preview_id = "preview-" + secrets.token_hex(24)
        self._previews[preview_id] = {"binding": binding, "context": copy.deepcopy(request["context"]),
                                     "result": result, "expiresAt": time.time() + result["expiresInSeconds"]}
        public = {key: result[key] for key in ("preview", "previewDigest", "expiresInSeconds")}
        public["previewId"] = preview_id
        return _success(request, workspace_context(ws, draft), public, "preview")

    def _confirm(self, request, auth, binding):
        _request(request, ("context", "previewId", "previewDigest", "decision"))
        ws, draft = self._expect(request["context"], needs_draft=True)
        identifier(request["previewId"])
        handle = self._previews.get(request["previewId"])
        require(handle is not None and handle["binding"] == binding, "REQUEST_FORBIDDEN")
        require(handle["context"] == request["context"], "STALE_CONTEXT")
        require(len(self._reviews) < 128 or handle.get("reviewId") in self._reviews,
                detail="审阅授权数量已达上限")
        result = self._gateway.confirm_review(draft["draftId"], auth=auth,
                    **self._review_args(request["context"], draft), decision=request["decision"],
                    preview_digest=request["previewDigest"],
                    confirmation_token=handle["result"]["confirmationToken"])
        if result["decision"] == "accept":
            self._reviews[result["reviewId"]] = {"binding": binding,
                   "context": copy.deepcopy(request["context"]), "result": result,
                   "expiresAt": self._gateway._session(**auth)["expires"]}
        handle["expiresAt"] = self._gateway._session(**auth)["expires"]
        handle["reviewId"] = result["reviewId"]
        current = self._draft(draft["draftId"])
        public = {key: result[key] for key in ("reviewId", "decision", "verifiedCodeRevision")}
        public["canPublish"] = (result["decision"] == "accept"
                                and current.get("reviewId") == result["reviewId"]
                                and current["status"] in ("review_approved", "publishing"))
        return _success(request, workspace_context(ws, current),
                        public, "review_" + result["decision"])

    def _publish(self, request, auth, binding):
        _request(request, ("context", "reviewId"))
        _, draft = self._expect(request["context"], needs_draft=True)
        identifier(request["reviewId"])
        grant = self._reviews.get(request["reviewId"])
        require(grant is not None and grant["binding"] == binding, "REQUEST_FORBIDDEN")
        require(grant["context"] == request["context"]
                and draft.get("reviewId") == request["reviewId"], "STALE_CONTEXT")
        envelope = self._service.publish_reviewed_graph(draft["draftId"],
                    publication_token=grant["result"]["publicationToken"],
                    expected_map_revision=request["context"]["baseMapRevision"])
        return _success(request, workspace_context(self._workspace(), self._draft(draft["draftId"])),
                        {"versionEnvelope": envelope, "currentVersionRef": version_reference(envelope)},
                        "published")

    def _status(self, request, auth, binding):
        _request(request, ("draftId",))
        draft = self._draft(request["draftId"])
        ws = self._workspace()
        grant = self._reviews.get(draft.get("reviewId"))
        context_current = (all(draft[k] == ws[k] for k in CONTEXT_FIELDS[:5])
                           and draft["baseMapRevision"] == ws["mapRevision"])
        can_retry = bool(grant and grant["binding"] == binding
                         and draft["status"] in ("review_approved", "publishing")
                         and context_current)
        recovery = ("same_session_retry" if can_retry else "awaiting_trusted_recovery"
                    if draft["status"] in ("review_approved", "publishing") else None)
        if draft["status"] == "review_approved" and not context_current:
            recovery = "context_refresh_required"
        return _success(request, workspace_context(self._workspace(), draft),
                        {"draftStatus": draft["status"], "reviewId": draft.get("reviewId"),
                         "publishedMapRevision": draft.get("publishedMapRevision"),
                         "canRetry": can_retry, "contextCurrent": context_current,
                         "recovery": recovery}, "publication_status")

    def _import(self, request, auth, binding):
        _request(request, ("context", "sourceRegistrationId", "versionRef"))
        require(self._source_registration_id is not None
                and request["sourceRegistrationId"] == self._source_registration_id,
                "REQUEST_FORBIDDEN")
        ws, _ = self._expect(request["context"])
        require(request["context"]["draftId"] is None)
        reference = request["versionRef"]
        fields(reference, VERSION_FIELDS)
        require(all(reference[key] == ws[key] for key in
                    ("mapId", "codeRepoId", "codeRevision")), "STALE_CONTEXT")
        require(self._service.publisher is not None, "PUBLICATION_FAILED")
        # Source selector resolves only to the server-registered publisher.
        # Read and check actual pinned Git bytes before any local import write.
        actual = GitPublisher.read_version(self._service.publisher.repo, ws["mapId"],
                         reference["mapRevision"], reference["mapSourceRevision"])
        require(version_reference(actual) == reference, "STALE_CONTEXT")
        self._service.import_git_version(self._workspace_id, map_revision=reference["mapRevision"],
                    map_source_revision=reference["mapSourceRevision"],
                    expected_map_revision=request["context"]["baseMapRevision"])
        result = self._view(request)
        result["status"] = "imported"
        return result


class CollaborationAPI(_ScopedSurface):
    """Server-issued workspace/role/exact-version capability; never a writer."""
    def __init__(self, service, workspace_id, *, role, allowed_map_revisions=()):
        super().__init__(service, workspace_id)
        require(role in ("C", "D"))
        require(isinstance(allowed_map_revisions, (tuple, list, set, frozenset)))
        require(all(isinstance(rev, str) and MAP_REV.fullmatch(rev) for rev in allowed_map_revisions))
        self._role = role
        self._versions = frozenset(allowed_map_revisions)

    def call(self, action, request):
        try:
            require(isinstance(action, str), "REQUEST_FORBIDDEN")
            canonical(request)
            request = copy.deepcopy(request)
            if action == "readContext":
                _request(request, optional=("draftId",))
                require(self._role == "C", "REQUEST_FORBIDDEN")
                snapshot = self._service.graph_snapshot(self._workspace_id)
                draft = self._draft(request["draftId"]) if "draftId" in request else None
                envelope = snapshot["versionEnvelope"]
                # The worker cannot obtain an ungranted formal packet by using latest.
                require(envelope is None or envelope["version"]["mapRevision"] in self._versions,
                        "REQUEST_FORBIDDEN")
                return _success(request, workspace_context(snapshot["workspace"], draft),
                       {"snapshot": snapshot, "draft": draft}, "context")
            if action in ("readExactVersion", "exportExactVersion"):
                _request(request, ("versionRef",))
                require(action != "exportExactVersion" or self._role == "D", "REQUEST_FORBIDDEN")
                fields(request["versionRef"], VERSION_FIELDS)
                require(request["versionRef"]["mapRevision"] in self._versions, "REQUEST_FORBIDDEN")
                envelope = self._exact(request["versionRef"])
                return _success(request, workspace_context(self._workspace()),
                                {"versionEnvelope": envelope}, "exact_version")
            if action == "validateProposal":
                _request(request, ("context", "proposal"))
                require(self._role == "C", "REQUEST_FORBIDDEN")
                self._expect(request["context"])
                proposal = self._service.validate_candidate_proposal(
                    proposal=request["proposal"], expected_context=request["context"])
                return _success(request, request["context"],
                    {"proposalId": proposal["proposalId"], "proposalDigest": proposal["proposalDigest"],
                     "candidateIds": [c["candidateId"] for c in proposal["candidates"]],
                     "unknowns": proposal["unknowns"], "writePerformed": False,
                     "validationScope": "structure_basis_and_bootstrap_evidence",
                     "selectedPatchGraphValidation": "deferred_to_atomic_save"}, "valid_candidate")
            raise WorkspaceError("REQUEST_FORBIDDEN")
        except (TypeError, KeyError, IndexError, AttributeError, RecursionError, OverflowError):
            return _error(request, WorkspaceError("INVALID_INPUT"))
        except WorkspaceError as exc:
            current = None
            if exc.code in ("REVISION_CONFLICT", "STALE_CONTEXT"):
                try:
                    current = self._current_context(request)
                except WorkspaceError:
                    pass
            return _error(request, exc, current)
