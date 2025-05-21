eel.expose(addToLog);
eel.expose(controlLoader);

function addToLog(text) {
    var div = document.getElementById('log');
    div.innerHTML += text + '<br>';
}

function controlLoader(mode){
    var loaderElement = document.getElementById('loader')

    if (mode == 1){
        loaderElement.style.visibility = "visible";
        console.log("loader visible")
    }
    else if (mode == 0){
        loaderElement.style.visibility = "hidden";
        console.log("loader hidden")
    }
}

document.getElementById('triggerSearch').addEventListener('submit', function(event) {
    event.preventDefault();
    eel.start_search();
});