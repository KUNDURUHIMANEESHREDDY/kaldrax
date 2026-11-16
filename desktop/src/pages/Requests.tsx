import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useApp } from "../store/useApp";
import { usePageTitle } from "../hooks/usePageTitle";
import { useToast } from "../hooks/useToast";
import {
  Avatar,
  Badge,
  Button,
  Card,
  ConfirmDialog,
  Drawer,
  EmptyState,
  Field,
  ItemThumb,
  Notice,
  PageHead,
  Pagination,
  SearchField,
  Segments,
  Textarea,
} from "../components/ui";
import { Modal } from "../components/ui";
import { RequestFormModal } from "../components/forms";
import { Icon } from "../components/Icons";
import { requestAvailability, requestValue } from "../lib/derive";
import {
  dateShort,
  dateTime,
  inr,
  inrCompact,
  num,
  priorityTone,
  relTime,
  requestStatusLabel,
  requestStatusTone,
} from "../lib/format";
import { canApproveRequests, canManageInventory } from "../lib/permissions";
import type { MaterialRequest } from "../lib/types";

/* ------------------------------------------------------------------ */
/* Shared pieces                                                       */
/* ------------------------------------------------------------------ */

function RequestHeader({ request }: { request: MaterialRequest }) {
  const { state } = useApp();
  const project = state.projects.find((p) => p.id === request.projectId);
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
      <Avatar name={request.requestedBy} size="lg" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap" }}>
          <span className="mono" style={{ fontSize: 11 }}>
            {request.id}
          </span>
          <Badge tone={requestStatusTone(request.status)} dot>
            {requestStatusLabel(request.status)}
          </Badge>
          <Badge tone={priorityTone(request.priority)}>{request.priority}</Badge>
        </div>
        <div style={{ fontSize: 14, fontWeight: 600, letterSpacing: "-0.3px", marginTop: 4 }}>
          {request.requestedBy}
        </div>
        <div style={{ fontSize: 10.5, color: "var(--muted)" }}>
          {project ? (
            <Link to={`/projects/${project.id}`} className="card__link">
              {project.name}
            </Link>
          ) : (
            request.projectId
          )}{" "}
          · submitted {relTime(request.createdAt)}
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 10, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--faint)" }}>
          Est. value
        </div>
        <div style={{ fontSize: 14, fontWeight: 600, letterSpacing: "-0.3px" }}>{inrCompact(requestValue(state, request))}</div>
      </div>
    </div>
  );
}

function RequestLines({ request, showAvailability }: { request: MaterialRequest; showAvailability?: boolean }) {
  const { state } = useApp();
  const availability = requestAvailability(state, request);
  return (
    <div className="approval-panel">
      {availability.map((line, index) => (
        <div className="approval-panel__item" key={line.item?.id ?? `line-${index}`}>
          <ItemThumb category={state.categories.find((c) => c.id === line.item?.categoryId)} size="sm" />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="cell-item__name truncate">{line.item?.name ?? "Item no longer exists"}</div>
            <div className="cell-item__sub mono">{line.item?.id ?? "—"}</div>
          </div>
          {showAvailability ? (
            line.ok ? (
              <Badge tone="green">In stock</Badge>
            ) : (
              <Badge tone="red">Short {line.shortfall}</Badge>
            )
          ) : null}
          <span className="req">
            <b>{num(line.qty)}</b> {line.item?.unit ?? "units"}
            {showAvailability ? <span style={{ display: "block", color: line.ok ? "var(--muted)" : "var(--red)" }}>{num(line.available)} available</span> : null}
          </span>
        </div>
      ))}
    </div>
  );
}

function RequestTimeline({ request }: { request: MaterialRequest }) {
  const steps = [
    { label: "Submitted", at: request.createdAt, who: request.requestedBy, done: true },
    {
      label: request.status === "rejected" ? "Rejected" : "Reviewed",
      at: request.reviewedAt,
      who: request.reviewedBy,
      done: Boolean(request.reviewedAt),
    },
    { label: "Issued", at: request.issuedAt, who: request.reviewedBy, done: Boolean(request.issuedAt) },
    { label: "Returned", at: request.returnedAt, who: undefined, done: Boolean(request.returnedAt) },
  ];
  return (
    <div className="timeline">
      {steps.map((s) => (
        <div className="timeline__item" key={s.label} style={s.done ? undefined : { opacity: 0.45 }}>
          <span className="timeline__marker">
            <Icon name={s.done ? "check" : "clock"} />
          </span>
          <div className="timeline__body">
            <p className="timeline__title">
              <b>{s.label}</b>
              {s.who ? ` · ${s.who}` : ""}
            </p>
            <p className="timeline__time">{s.at ? dateTime(s.at) : "Waiting"}</p>
          </div>
        </div>
      ))}
      {request.rejectReason ? (
        <div className="timeline__item">
          <span className="timeline__marker" style={{ background: "var(--red-soft)", color: "var(--red)" }}>
            <Icon name="x" />
          </span>
          <div className="timeline__body">
            <p className="timeline__title">
              <b>Rejection reason</b>
            </p>
            <p className="timeline__time">{request.rejectReason}</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Reject dialog                                                       */
/* ------------------------------------------------------------------ */

function RejectModal({
  open,
  onClose,
  request,
}: {
  open: boolean;
  onClose: () => void;
  request?: MaterialRequest;
}) {
  if (!open || !request) return null;
  return <RejectForm key={request.id} onClose={onClose} request={request} />;
}

function RejectForm({ onClose, request }: { onClose: () => void; request: MaterialRequest }) {
  const { rejectRequest } = useApp();
  const toast = useToast();
  const [reason, setReason] = useState("");

  const submit = () => {
    const result = rejectRequest(request.id, reason);
    if (!result.ok) {
      toast.error("Request not rejected", result.message);
      return;
    }
    toast.success("Request rejected", `${request.id} was returned to ${request.requestedBy}.`);
    onClose();
  };

  return (
    <Modal
      open={true}
      onClose={onClose}
      title={`Reject ${request.id}?`}
      sub={`${request.requestedBy} · ${request.lines.length} line item${request.lines.length === 1 ? "" : "s"}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="danger" onClick={submit} icon="x">
            Reject request
          </Button>
        </>
      }
    >
      <Field label="Reason" required hint="Shared with the student so they can correct and resubmit." htmlFor="reject-reason">
        <Textarea
          id="reject-reason"
          rows={4}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. Requested quantity exceeds the project's bill of materials."
          autoFocus
        />
      </Field>
    </Modal>
  );
}

/* ------------------------------------------------------------------ */
/* Pending approvals                                                   */
/* ------------------------------------------------------------------ */

export function PendingRequests() {
  usePageTitle("Pending requests");
  const { state, role, approveRequest, issueRequest, cancelRequest } = useApp();
  const toast = useToast();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(params.get("new") === "1");
  const [rejectFor, setRejectFor] = useState<MaterialRequest | undefined>();
  const [confirmIssue, setConfirmIssue] = useState<MaterialRequest | undefined>();
  const [cancelFor, setCancelFor] = useState<MaterialRequest | undefined>();

  const canApprove = canApproveRequests(role);
  const canIssue = canManageInventory(role);

  useEffect(() => {
    const next = new URLSearchParams(params);
    if (createOpen) next.set("new", "1");
    else next.delete("new");
    if (next.toString() !== params.toString()) setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [createOpen]);

  const pending = useMemo(() => {
    const q = query.trim().toLowerCase();
    return state.requests
      .filter((r) => r.status === "pending")
      .filter((r) => {
        if (!q) return true;
        return (
          r.id.toLowerCase().includes(q) ||
          r.requestedBy.toLowerCase().includes(q) ||
          r.note.toLowerCase().includes(q) ||
          r.lines.some((l) => (state.items.find((i) => i.id === l.itemId)?.name ?? "").toLowerCase().includes(q))
        );
      })
      .sort((a, b) => {
        const rank = { urgent: 0, high: 1, normal: 2, low: 3 } as const;
        const diff = rank[a.priority] - rank[b.priority];
        return diff !== 0 ? diff : new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
      });
  }, [state.requests, state.items, query]);

  const selected = pending.find((r) => r.id === selectedId) ?? pending[0];

  const handleApprove = (request: MaterialRequest) => {
    const result = approveRequest(request.id);
    if (!result.ok) toast.error("Request not approved", result.message);
    else toast.success("Request approved", `${request.id} is ready to issue.`);
  };

  const handleIssue = () => {
    if (!confirmIssue) return;
    const result = issueRequest(confirmIssue.id);
    if (!result.ok) toast.error("Materials not issued", result.message);
    else {
      toast.success("Materials issued", `${confirmIssue.id} was issued and the ledger updated.`);
      navigate("/requests/approved");
    }
    setConfirmIssue(undefined);
  };

  const handleCancel = () => {
    if (!cancelFor) return;
    const result = cancelRequest(cancelFor.id);
    if (!result.ok) toast.error("Request not cancelled", result.message);
    else toast.success("Request cancelled", `${cancelFor.id} was withdrawn.`);
    setCancelFor(undefined);
  };

  const shortageCount = pending.filter((r) => requestAvailability(state, r).some((a) => !a.ok)).length;

  return (
    <>
      <PageHead
        title="Pending requests"
        sub="Review material requests from PBL teams before anything leaves the store."
        actions={
          <>
            {canApprove && shortageCount > 0 ? <Badge tone="red">{shortageCount} with shortages</Badge> : null}
            <Button variant="primary" size="sm" icon="plus" onClick={() => setCreateOpen(true)}>
              New request
            </Button>
          </>
        }
      />

      <div className="filter-bar">
        <Segments
          items={[
            { to: "/requests/pending", label: "Pending", count: state.requests.filter((r) => r.status === "pending").length },
            { to: "/requests/approved", label: "Approved", count: state.requests.filter((r) => r.status === "approved").length },
            { to: "/requests/history", label: "History" },
          ]}
        />
        <span className="toolbar__spacer" />
        <SearchField value={query} onChange={setQuery} placeholder="Search requests…" />
      </div>

      {pending.length === 0 ? (
        <EmptyState
          icon="check-circle"
          title="No requests waiting"
          text="Every submitted request has been reviewed. New ones will land here for approval."
          action={
            <Button size="sm" variant="secondary" icon="plus" onClick={() => setCreateOpen(true)}>
              Submit a request
            </Button>
          }
        />
      ) : (
        <div className="grid">
          <div className="col-5">
            <Card flush>
              <div style={{ padding: "16px 16px 8px" }}>
                <h2 className="card__title">Queue</h2>
                <p className="card__sub">
                  {pending.length} waiting · urgent first
                </p>
              </div>
              <div style={{ padding: "0 8px 10px" }}>
                {pending.map((r) => {
                  const active = selected?.id === r.id;
                  const shortage = requestAvailability(state, r).some((a) => !a.ok);
                  const project = state.projects.find((p) => p.id === r.projectId);
                  return (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => setSelectedId(r.id)}
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: 10,
                        width: "100%",
                        textAlign: "left",
                        padding: "10px 10px",
                        borderRadius: "var(--r-md)",
                        background: active ? "var(--surface-2)" : undefined,
                        boxShadow: active ? "inset 0 0 0 1px var(--line-strong)" : undefined,
                      }}
                    >
                      <Avatar name={r.requestedBy} />
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <span className="mono" style={{ fontSize: 10.5 }}>
                            {r.id}
                          </span>
                          <Badge tone={priorityTone(r.priority)}>{r.priority}</Badge>
                          {shortage ? <Badge tone="red">Short</Badge> : null}
                        </span>
                        <span style={{ display: "block", fontSize: 11.5, fontWeight: 500, marginTop: 2 }} className="truncate">
                          {project?.name ?? r.projectId}
                        </span>
                        <span style={{ display: "block", fontSize: 10, color: "var(--muted)" }} className="truncate">
                          {r.requestedBy} · {r.lines.length} line{r.lines.length === 1 ? "" : "s"} · {relTime(r.createdAt)}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </Card>
          </div>

          <div className="col-7">
            {selected ? (
              <Card>
                <RequestHeader request={selected} />

                {selected.note ? (
                  <p style={{ fontSize: 11.5, color: "var(--ink-3)", marginTop: 12, lineHeight: 1.65 }}>{selected.note}</p>
                ) : null}

                <div style={{ marginTop: 16 }}>
                  <div className="section-head" style={{ marginBottom: 8 }}>
                    <div>
                      <h3 className="card__title" style={{ fontSize: 13 }}>
                        Requested materials
                      </h3>
                      <p className="card__sub">Availability checked against current stock</p>
                    </div>
                    <Badge outline>{inr(requestValue(state, selected))}</Badge>
                  </div>
                  <RequestLines request={selected} showAvailability />
                </div>

                {requestAvailability(state, selected).some((a) => !a.ok) ? (
                  <div style={{ marginTop: 14 }}>
                    <Notice tone="red" icon="alert-triangle">
                      One or more lines exceed available stock. Receive stock or reject the request with a reason.
                    </Notice>
                  </div>
                ) : null}

                <div style={{ display: "flex", gap: 8, marginTop: 18, flexWrap: "wrap" }}>
                  {canApprove ? (
                    <>
                      <Button
                        variant="primary"
                        icon="check"
                        onClick={() => handleApprove(selected)}
                        disabled={selected.status !== "pending"}
                      >
                        Approve request
                      </Button>
                      <Button variant="danger-soft" icon="x" onClick={() => setRejectFor(selected)}>
                        Reject
                      </Button>
                    </>
                  ) : null}
                  {canIssue && selected.status === "approved" ? (
                    <Button variant="primary" icon="upload" onClick={() => setConfirmIssue(selected)}>
                      Issue materials
                    </Button>
                  ) : null}
                  {role === "student" ? (
                    <Button variant="ghost" icon="trash" onClick={() => setCancelFor(selected)}>
                      Withdraw
                    </Button>
                  ) : null}
                  <span className="spacer" />
                  <Link to={`/projects/${selected.projectId}`} className="card__link" style={{ alignSelf: "center" }}>
                    Open project <Icon name="arrow-right" />
                  </Link>
                </div>

                <div className="divider" style={{ margin: "20px 0 16px" }} />
                <h3 className="card__title" style={{ fontSize: 13, marginBottom: 10 }}>
                  Workflow
                </h3>
                <RequestTimeline request={selected} />
              </Card>
            ) : null}
          </div>
        </div>
      )}

      <RequestFormModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(id) => {
          if (id) setSelectedId(id);
          navigate("/requests/pending");
        }}
      />
      <RejectModal open={Boolean(rejectFor)} onClose={() => setRejectFor(undefined)} request={rejectFor} />
      <ConfirmDialog
        open={Boolean(confirmIssue)}
        title={`Issue materials for ${confirmIssue?.id ?? "request"}?`}
        message="This removes the requested quantities from stock and records a ledger entry for every line. It cannot be undone; use returns to reconcile leftovers."
        confirmLabel="Issue materials"
        tone="primary"
        onConfirm={handleIssue}
        onClose={() => setConfirmIssue(undefined)}
      />
      <ConfirmDialog
        open={Boolean(cancelFor)}
        title={`Withdraw ${cancelFor?.id ?? "request"}?`}
        message="Withdrawing removes the request from the queue. The team will need to submit a new one."
        confirmLabel="Withdraw request"
        onConfirm={handleCancel}
        onClose={() => setCancelFor(undefined)}
      />
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Approved                                                            */
/* ------------------------------------------------------------------ */

export function ApprovedRequests() {
  usePageTitle("Approved requests");
  const { state, role, issueRequest } = useApp();
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);
  const [confirmFor, setConfirmFor] = useState<MaterialRequest | undefined>();

  const canIssue = canManageInventory(role);

  const approved = useMemo(() => {
    const q = query.trim().toLowerCase();
    return state.requests
      .filter((r) => r.status === "approved")
      .filter((r) => {
        if (!q) return true;
        return (
          r.id.toLowerCase().includes(q) ||
          r.requestedBy.toLowerCase().includes(q) ||
          r.lines.some((l) => (state.items.find((i) => i.id === l.itemId)?.name ?? "").toLowerCase().includes(q))
        );
      })
      .sort((a, b) => new Date(b.reviewedAt ?? b.createdAt).getTime() - new Date(a.reviewedAt ?? a.createdAt).getTime());
  }, [state.requests, state.items, query]);

  const detail = detailId ? state.requests.find((r) => r.id === detailId) : undefined;

  const handleIssue = () => {
    if (!confirmFor) return;
    const result = issueRequest(confirmFor.id);
    if (!result.ok) toast.error("Materials not issued", result.message);
    else toast.success("Materials issued", `${confirmFor.id} moved to the ledger.`);
    setConfirmFor(undefined);
  };

  const totalUnits = approved.reduce((s, r) => s + r.lines.reduce((x, l) => x + l.qty, 0), 0);
  const totalValue = approved.reduce((s, r) => s + requestValue(state, r), 0);

  return (
    <>
      <PageHead
        title="Approved requests"
        sub="Cleared for issue. Hand over the materials to close each request."
        actions={canIssue ? <Badge tone="blue">{approved.length} ready to issue</Badge> : null}
      />

      <div className="filter-bar">
        <Segments
          items={[
            { to: "/requests/pending", label: "Pending", count: state.requests.filter((r) => r.status === "pending").length },
            { to: "/requests/approved", label: "Approved", count: approved.length },
            { to: "/requests/history", label: "History" },
          ]}
        />
        <span className="toolbar__spacer" />
        <SearchField value={query} onChange={setQuery} placeholder="Search approved requests…" />
      </div>

      {approved.length > 0 ? (
        <div className="mini-stats" style={{ marginBottom: "var(--gutter)" }}>
          <div className="mini-stat">
            <span>Ready to issue</span>
            <b>{num(approved.length)}</b>
            <em>Reviewed and cleared</em>
          </div>
          <div className="mini-stat">
            <span>Units committed</span>
            <b>
              {num(totalUnits)} <small>units</small>
            </b>
            <em>Across all approved lines</em>
          </div>
          <div className="mini-stat">
            <span>Estimated value</span>
            <b>{inrCompact(totalValue)}</b>
            <em>At current unit cost</em>
          </div>
          <div className="mini-stat">
            <span>Oldest waiting</span>
            <b>{approved[approved.length - 1] ? relTime(approved[approved.length - 1].reviewedAt ?? approved[approved.length - 1].createdAt) : "—"}</b>
            <em>Since approval</em>
          </div>
        </div>
      ) : null}

      {approved.length === 0 ? (
        <EmptyState
          icon="check-circle"
          title="Nothing waiting to be issued"
          text="Approved requests appear here until their materials are handed over."
          action={
            <Link to="/requests/pending" className="btn btn--secondary btn--sm">
              Review pending requests
            </Link>
          }
        />
      ) : (
        <Card flush>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Request</th>
                  <th>Project</th>
                  <th>Requested by</th>
                  <th className="num">Lines</th>
                  <th className="num">Value</th>
                  <th>Approved</th>
                  <th>Availability</th>
                  <th className="cell-actions" />
                </tr>
              </thead>
              <tbody>
                {approved.map((r) => {
                  const project = state.projects.find((p) => p.id === r.projectId);
                  const short = requestAvailability(state, r).some((a) => !a.ok);
                  return (
                    <tr key={r.id} onClick={() => setDetailId(r.id)} style={{ cursor: "pointer" }}>
                      <td>
                        <div className="mono">{r.id}</div>
                        <div className="cell-item__sub">{relTime(r.createdAt)}</div>
                      </td>
                      <td className="truncate" style={{ maxWidth: 200 }}>
                        {project?.name ?? r.projectId}
                      </td>
                      <td>
                        <div className="cell-item">
                          <Avatar name={r.requestedBy} size="sm" />
                          <span>{r.requestedBy}</span>
                        </div>
                      </td>
                      <td className="num">{r.lines.length}</td>
                      <td className="num">{inr(requestValue(state, r))}</td>
                      <td className="muted">{r.reviewedAt ? dateShort(r.reviewedAt) : "—"}</td>
                      <td>{short ? <Badge tone="red">Short</Badge> : <Badge tone="green">Ready</Badge>}</td>
                      <td className="cell-actions" onClick={(e) => e.stopPropagation()}>
                        <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                          <Button size="sm" variant="secondary" icon="eye" onClick={() => setDetailId(r.id)}>
                            View
                          </Button>
                          {canIssue ? (
                            <Button size="sm" variant="primary" icon="upload" onClick={() => setConfirmFor(r)}>
                              Issue
                            </Button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Drawer
        open={Boolean(detail)}
        onClose={() => setDetailId(null)}
        title={detail?.id ?? "Request"}
        sub={detail ? `Approved ${detail.reviewedAt ? dateShort(detail.reviewedAt) : ""}` : undefined}
        width={470}
        footer={
          detail && canIssue ? (
            <Button variant="primary" size="sm" icon="upload" onClick={() => setConfirmFor(detail)}>
              Issue materials
            </Button>
          ) : undefined
        }
      >
        {detail ? (
          <>
            <RequestHeader request={detail} />
            {detail.note ? (
              <p style={{ fontSize: 11.5, color: "var(--ink-3)", marginTop: 12, lineHeight: 1.65 }}>{detail.note}</p>
            ) : null}
            <div style={{ marginTop: 16 }}>
              <RequestLines request={detail} showAvailability />
            </div>
            <div className="divider" style={{ margin: "18px 0" }} />
            <RequestTimeline request={detail} />
          </>
        ) : null}
      </Drawer>

      <ConfirmDialog
        open={Boolean(confirmFor)}
        title={`Issue materials for ${confirmFor?.id ?? "request"}?`}
        message="Stock is deducted for each line and a ledger entry is created. Leftovers can be returned from the project page."
        confirmLabel="Issue materials"
        tone="primary"
        onConfirm={handleIssue}
        onClose={() => setConfirmFor(undefined)}
      />
    </>
  );
}

/* ------------------------------------------------------------------ */
/* History                                                             */
/* ------------------------------------------------------------------ */

type StatusFilter = "all" | "pending" | "approved" | "issued" | "rejected";

export function RequestHistory() {
  usePageTitle("Request history");
  const { state } = useApp();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [detailId, setDetailId] = useState<string | null>(null);

  const counts = useMemo(() => {
    const map: Record<string, number> = { all: state.requests.length, pending: 0, approved: 0, issued: 0, rejected: 0, returned: 0 };
    state.requests.forEach((r) => {
      map[r.status] = (map[r.status] ?? 0) + 1;
    });
    return map;
  }, [state.requests]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return state.requests
      .filter((r) => (status === "all" ? true : r.status === status))
      .filter((r) => {
        if (!q) return true;
        return (
          r.id.toLowerCase().includes(q) ||
          r.requestedBy.toLowerCase().includes(q) ||
          r.note.toLowerCase().includes(q) ||
          r.lines.some((l) => (state.items.find((i) => i.id === l.itemId)?.name ?? "").toLowerCase().includes(q))
        );
      })
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
  }, [state.requests, state.items, query, status]);

  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const visible = rows.slice((safePage - 1) * pageSize, safePage * pageSize);
  const detail = detailId ? state.requests.find((r) => r.id === detailId) : undefined;

  return (
    <>
      <PageHead
        title="Request history"
        sub="Every material request raised this semester, from submission through issue."
        actions={
          <Link to="/requests/pending?new=1" className="btn btn--primary btn--sm">
            <Icon name="plus" /> New request
          </Link>
        }
      />

      <div className="filter-bar">
        <Segments
          items={[
            { to: "/requests/pending", label: "Pending", count: counts.pending },
            { to: "/requests/approved", label: "Approved", count: counts.approved },
            { to: "/requests/history", label: "History" },
          ]}
        />
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
        {(["all", "pending", "approved", "issued", "rejected"] as const).map((s) => (
          <button
            key={s}
            type="button"
            className={`filter-chip${status === s ? " is-active" : ""}`}
            style={status === s ? { background: "var(--ink)", borderColor: "var(--ink)", color: "#fff" } : undefined}
            onClick={() => {
              setStatus(s);
              setPage(1);
            }}
          >
            {s === "all" ? "All statuses" : requestStatusLabel(s)}
            <span className="segmented__count" style={{ opacity: 0.7 }}>
              {counts[s] ?? 0}
            </span>
          </button>
        ))}
      </div>

      <div className="filter-bar">
        <SearchField
          value={query}
          onChange={(v) => {
            setQuery(v);
            setPage(1);
          }}
          placeholder="Search request, student or material…"
          className="toolbar__search"
        />
        <span className="toolbar__spacer" />
        <span className="filter-count">
          {rows.length} of {state.requests.length} requests
        </span>
      </div>

      <Card flush>
        {visible.length === 0 ? (
          <EmptyState icon="inbox" title="No requests match" text="Try another status or search term." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Request</th>
                  <th>Project</th>
                  <th>Requested by</th>
                  <th>Priority</th>
                  <th className="num">Lines</th>
                  <th className="num">Value</th>
                  <th>Status</th>
                  <th className="num">Submitted</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => {
                  const project = state.projects.find((p) => p.id === r.projectId);
                  return (
                    <tr key={r.id} onClick={() => setDetailId(r.id)} style={{ cursor: "pointer" }}>
                      <td>
                        <div className="mono">{r.id}</div>
                        <div className="cell-item__sub truncate" style={{ maxWidth: 180 }}>
                          {r.note || "No note"}
                        </div>
                      </td>
                      <td className="truncate" style={{ maxWidth: 180 }}>
                        {project?.name ?? r.projectId}
                      </td>
                      <td>
                        <div className="cell-item">
                          <Avatar name={r.requestedBy} size="sm" />
                          <span className="truncate" style={{ maxWidth: 120 }}>
                            {r.requestedBy}
                          </span>
                        </div>
                      </td>
                      <td>
                        <Badge tone={priorityTone(r.priority)}>{r.priority}</Badge>
                      </td>
                      <td className="num">{r.lines.length}</td>
                      <td className="num">{inr(requestValue(state, r))}</td>
                      <td>
                        <Badge tone={requestStatusTone(r.status)} dot>
                          {requestStatusLabel(r.status)}
                        </Badge>
                      </td>
                      <td className="num muted">{dateShort(r.createdAt)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {rows.length > 0 ? (
          <Pagination
            page={safePage}
            pageSize={pageSize}
            total={rows.length}
            onPage={setPage}
            onPageSize={(n) => {
              setPageSize(n);
              setPage(1);
            }}
          />
        ) : null}
      </Card>

      <Drawer
        open={Boolean(detail)}
        onClose={() => setDetailId(null)}
        title={detail?.id ?? "Request"}
        sub={detail ? `${detail.lines.length} line item${detail.lines.length === 1 ? "" : "s"}` : undefined}
        width={470}
      >
        {detail ? (
          <>
            <RequestHeader request={detail} />
            {detail.note ? (
              <p style={{ fontSize: 11.5, color: "var(--ink-3)", marginTop: 12, lineHeight: 1.65 }}>{detail.note}</p>
            ) : null}
            <div style={{ marginTop: 16 }}>
              <RequestLines request={detail} showAvailability={detail.status === "pending"} />
            </div>
            <div className="divider" style={{ margin: "18px 0" }} />
            <RequestTimeline request={detail} />
          </>
        ) : null}
      </Drawer>
    </>
  );
}
