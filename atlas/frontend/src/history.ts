// Pure back/forward document history for the inspect drawer. No DOM: the
// drawer owns rendering, this owns only the stacks, so it is unit-testable.
export class DocHistory {
  private backStack: string[] = [];
  private fwdStack: string[] = [];
  private current: string | null = null;

  /** Open a fresh root document (from a lens): history starts over. */
  visitRoot(path: string): void {
    this.backStack = [];
    this.fwdStack = [];
    this.current = path;
  }

  /** In-drawer navigation (wikilink): pushes the current doc on the back stack. */
  visit(path: string): void {
    if (this.current !== null) this.backStack.push(this.current);
    this.fwdStack = [];
    this.current = path;
  }

  back(): string | null {
    const prev = this.backStack.pop();
    if (prev === undefined) return null;
    if (this.current !== null) this.fwdStack.push(this.current);
    this.current = prev;
    return prev;
  }

  forward(): string | null {
    const next = this.fwdStack.pop();
    if (next === undefined) return null;
    if (this.current !== null) this.backStack.push(this.current);
    this.current = next;
    return next;
  }

  get canBack(): boolean {
    return this.backStack.length > 0;
  }

  get canForward(): boolean {
    return this.fwdStack.length > 0;
  }

  reset(): void {
    this.backStack = [];
    this.fwdStack = [];
    this.current = null;
  }
}
