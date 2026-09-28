/** Rudimentary Markdown rendering for long free-text fields (notes, particularities). */
import MarkdownIt from "markdown-it";

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  typographer: false,
});

// Force every link (markdown syntax or auto-linkified) to open in a new tab
// without granting it access to window.opener.
const defaultLinkOpen =
  md.renderer.rules.link_open ||
  function (tokens, idx, options, _env, self) {
    return self.renderToken(tokens, idx, options);
  };

md.renderer.rules.link_open = function (tokens, idx, options, env, self) {
  const token = tokens[idx];
  token.attrSet("target", "_blank");
  token.attrSet("rel", "noopener noreferrer");
  return defaultLinkOpen(tokens, idx, options, env, self);
};

export function renderMarkdown(text) {
  if (!text) return "";
  return md.render(String(text));
}
