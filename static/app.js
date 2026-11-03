// The symbol buttons need JavaScript, so they are hidden in the HTML and shown
// here. Without JavaScript the forms still work: ASCII spellings (~ & | -> <->)
// can be typed instead. Pages with several inputs (equivalence, argument) insert
// into whichever formula box was focused last.
document.addEventListener("DOMContentLoaded", () => {
    const palette = document.getElementById("symbols");
    const inputs = Array.from(document.querySelectorAll(".formula-input"));
    if (!palette || inputs.length === 0) {
        return;
    }

    let target = inputs[0];
    inputs.forEach((input) => {
        input.addEventListener("focus", () => {
            target = input;
        });
    });

    palette.hidden = false;
    palette.querySelectorAll("[data-insert]").forEach((button) => {
        button.addEventListener("click", () => {
            // Replace the selection (or insert at the caret) and leave the
            // caret just after the new text.
            target.setRangeText(button.dataset.insert, target.selectionStart, target.selectionEnd, "end");
            target.focus();
        });
    });
});