// A tiny stand-in for the browser DOM, enough for static/js/render*.js to build cards in Node.

export class FakeNode {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.attrs = {};
    this.className = "";
    this.listeners = {};
    this.ownText = null;
  }
  append(...children) {
    for (const child of children) this.children.push(child);
  }
  setAttribute(key, value) { this.attrs[key] = value; }
  addEventListener(type, handler) { this.listeners[type] = handler; }
  get textContent() { return this.ownText ?? this.children.map((c) => c.textContent).join(""); }
  set textContent(value) { this.ownText = value; this.children = []; }
}

class FakeText extends FakeNode {
  constructor(text) { super("#text"); this.ownText = text; }
}

globalThis.Node = FakeNode;
globalThis.document = {
  createElement: (tag) => new FakeNode(tag),
  createElementNS: (ns, tag) => new FakeNode(tag),
  createTextNode: (text) => new FakeText(text),
};

export function all(node, test, found = []) {
  if (test(node)) found.push(node);
  for (const child of node.children || []) all(child, test, found);
  return found;
}
export const byClass = (node, cls) => all(node, (n) => (n.className || "").split(" ").includes(cls));
export const byTag = (node, tag) => all(node, (n) => n.tag === tag);

export function holderOf(parts) {
  const holder = new FakeNode("div");
  holder.append(...parts);
  return holder;
}
