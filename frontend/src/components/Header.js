export class Header {
  constructor(container) {
    this.container = container;
    this.workspace = document.getElementById('workspace');
  }

  init() {
    const toggle = this.container.querySelector('#menuToggle');
    if (toggle && this.workspace) {
      toggle.addEventListener('click', () => {
        this.workspace.classList.toggle('collapsed');
      });
    }
  }
}
