// Pure evidence-link decision for the review change list (UI-01).
//
// The /api/evidence endpoint only accepts paths declared in the current map
// (otherwise 400) that also exist at the requested revision (otherwise 404).
// This decision picks, per change type, which (path, revision) evidence
// views are valid — and returns none when none are, so the UI never
// presents a broken 400/404 link as valid evidence:
//   ADDED / MODIFIED: the file's content context is the target revision.
//   DELETED: the content context is the base revision — never the target.
//   RENAMED: the old path at base AND the new path at target.
// Only map-declared paths produce evidence views. The B facts badge column
// is independent of this decision.
function evidenceTargetsFor(change, declaredPaths) {
  const declared = declaredPaths instanceof Set ? declaredPaths : new Set(declaredPaths || []);
  const targets = [];
  // Git name-status codes carry similarity suffixes for renames/copies
  // (R100, C75, ...), so the prefix — not an exact match — identifies them.
  if (typeof change.code === "string" && change.code.startsWith("R")) {
    if (change.oldPath && declared.has(change.oldPath)) {
      targets.push({ path: change.oldPath, revision: "base" });
    }
    if (declared.has(change.path)) {
      targets.push({ path: change.path, revision: "target" });
    }
    return targets;
  }
  if (!declared.has(change.path)) {
    return targets;
  }
  if (change.code === "D") {
    targets.push({ path: change.path, revision: "base" });
  } else {
    // A / M: the diff guarantees the path exists at the target revision.
    targets.push({ path: change.path, revision: "target" });
  }
  return targets;
}

// Map evidence paths from a /api/snapshot payload (the same declaration set
// the /api/evidence endpoint validates against).
function mapEvidencePaths(snapshot) {
  const paths = new Set();
  for (const node of (snapshot && snapshot.nodes) || []) {
    for (const item of node.evidence || []) {
      if (item && item.path) paths.add(item.path);
    }
  }
  return paths;
}
