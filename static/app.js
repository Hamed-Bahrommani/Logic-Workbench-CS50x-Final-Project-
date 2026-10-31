// The symbol buttons need JavaScript, so they are hidden in the HTML and shown
// here. Without JavaScript the form still works: ASCII spellings (~ & | -> <->)
// can be typed instead.
document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("formula");
    const palette = document.getElementById("symbols");
    if (!input || !palette) {
        return;
    }

    palette.hidden = false;
    palette.querySelectorAll("[data-insert]").forEach((button) => {
        button.addEventListener("click", () => {
            // Replace the selection (or insert at the caret) and leave the
            // caret just after the new text.
            input.setRangeText(button.dataset.insert, input.selectionStart, input.selectionEnd, "end");
            input.focus();
        });
    });
});