// assets/mito_disable.js
 
function disableDuplicateRename(e) {
  // Get the clicked element
  const el = e.target;
  if (!(el instanceof HTMLElement)) return;
 
  const txt = el.textContent && el.textContent.trim();
  if (txt === 'Duplicate' || txt === 'Rename' || txt === 'Delete'|| txt=='df1') {
    // Optionally: further check that this is inside a Mito sheet-tab menu.
    // If you know e.g. that the menu's container has class "mito-sheet-tab-menu", you could do:
    // if (!el.closest('.mito-sheet-tab-menu')) return;
    // But if you don't know any container, skip this check.
 
    // Prevent the default behavior and stop propagation
    e.stopImmediatePropagation();
    e.preventDefault();
    // Optionally give user feedback, e.g. console.log or a toast
    // console.log("Mito Duplicate/Rename disabled");
  }
}
 
// Attach at capture phase so you intercept before other handlers
document.addEventListener('click', disableDuplicateRename, true);


