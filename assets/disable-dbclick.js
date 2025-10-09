document.addEventListener('DOMContentLoaded', function () {
  // Utility: check if an element’s textContent (trimmed) is exactly 'df1' and rename it.
  function renameIfTextIsDf1(el) {
    // Only consider element nodes
    if (el.nodeType !== Node.ELEMENT_NODE) return;
    // If the element has child elements, textContent includes all children; 
    // if you want to only rename leaf nodes, uncomment the children-length check:
    // if (el.children.length > 0) return;
    
    const txt = el.textContent && el.textContent.trim();
    if (el.closest('.tab-content')) {
      const p = el.querySelector('p');
      const txt = p.textContent && p.textContent.trim();
      if (txt === 'df1') {
        p.textContent = 'Options';
        console.log('Renamed <p> from "df1" to "options":', p);
        return true;
      }
      
      // If you had event listeners or data tied to the old text, consider re-binding or updating data here.
      console.log('Renamed element text from "df1" to "Options":', el);
    }
  }
 
  // 1. Initial pass: scan existing elements in the DOM
  //    For performance, if you know a container where these occur, replace document.body with that container.
  document.querySelectorAll('*').forEach(renameIfTextIsDf1);
 
  // 2. Set up MutationObserver to catch future additions or text changes
  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      if (mutation.type === 'childList') {
        // New nodes added or removed
        mutation.addedNodes.forEach(node => {
          // If the added node is an element, check it and its descendants
          if (node.nodeType === Node.ELEMENT_NODE) {
            renameIfTextIsDf1(node);
            // Descendants:
            node.querySelectorAll('*').forEach(renameIfTextIsDf1);
          }
        });
        // We don't need to handle removedNodes for renaming.
      }
      else if (mutation.type === 'characterData') {
        // A text node changed. Its parent element’s textContent might now be 'df1'.
        // mutation.target is a text node.
        const parent = mutation.target.parentNode;
        if (parent && parent.nodeType === Node.ELEMENT_NODE) {
          // If parent has no child elements (i.e., only this text node), this is straightforward.
          // But if parent has multiple text nodes or mixed children, textContent includes all; 
          // this simple check still works if the entire textContent trimmed is exactly 'df1'.
          const txt = parent.textContent && parent.textContent.trim();
          if (txt === 'df1') {
            parent.textContent = 'Options';
            console.log('Renamed via characterData observer:', parent);
          }
        }
      }
      // You could also observe attribute changes if you expect 'df1' might appear as an attribute value 
      // (e.g., title or data-*), but here we focus on visible text.
    }
  });
 
  observer.observe(document.body, {
    childList: true,      // watch for added/removed child nodes
    subtree: true,        // watch the entire subtree
    characterData: true,  // watch for changes to text nodes
    // attribute: false,   // not needed here
    // attributeFilter: [...], // if watching specific attributes
  });
 
  // If at some point you want to stop observing:
  // observer.disconnect();
 
 
  // 3. (Optional) Integrate with your dblclick-blocking logic.
  //    If you previously blocked dblclick when text was 'df1', after renaming, you might instead
  //    block based on 'Options' or other conditions.
  document.body.addEventListener('dblclick', function (e) {
    const el = e.target;
    const txt = el.textContent && el.textContent.trim();
    // Example: block dblclick on certain texts, including the newly renamed 'Options':
    if (
      e.target.closest('.tab.tab-selected.cursor-pointer')
      || txt === 'Duplicate'
      || txt === 'Rename'
      || txt === 'Delete'
      || txt === 'Options'  // formerly 'df1'
    ) {
      e.preventDefault();
      e.stopPropagation();
      console.log('Double-click disabled on element with text:', txt, el);
    }
  }, true);

  document.body.addEventListener('contextmenu', function (e) {
    const el = e.target;
    
    // Example: block dblclick on certain texts, including the newly renamed 'Options':
    if (
      e.target.closest('.mito-sheet-and-formula-bar-container') // formerly 'df1'
    ) {
      e.preventDefault();
      e.stopPropagation();
      console.log('Double-click disabled on element with text:', txt, el);
    }
  }, true);
 
});
 