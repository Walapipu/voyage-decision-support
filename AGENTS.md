# Project working rules

- Work on a feature branch. Never merge or push changes to main without the user's explicit request.
- Layout quality is an acceptance requirement: no overlapping text, captions, charts, controls or cards on any page. Use consistent spacing and line heights. Keep page scrolling inside the designated content panels.
- Do not force fixed heights or flex shrinking onto content-sized text, tabs or report sections. Restrict viewport sizing to the app shell and explicitly designated scrolling panels.
- For UI changes, check all navigation pages, dark/light themes and narrow/wide viewports. Verify caption/expander boundaries and new-chat behaviour with a pending error, history and a draft. Record what was actually verified; do not promise absence of future bugs.
- Keep OpenRouter keys out of tracked files and logs. Local secrets are ignored; cloud secrets must be configured on the hosting service.
