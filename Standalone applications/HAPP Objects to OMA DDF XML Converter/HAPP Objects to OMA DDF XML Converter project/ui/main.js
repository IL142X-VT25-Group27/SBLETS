eel.expose(addToLog);

function addToLog(text) {
    var div = document.getElementById('log');
    div.innerHTML += text + '<br>';
}

function addToLogClean(text) {
    var div = document.getElementById('logClean');
    div.innerHTML += text + '<br>';
}

document.getElementById('uploadForm').addEventListener('submit', function(event) {
    event.preventDefault();

    var fileInput = document.getElementById('fileInput');
    var file = fileInput.files[0];

    if (file) {
        var reader = new FileReader();
        reader.onload = function(event) {
            var fileData = event.target.result;
            eel.uploadFile(file.name, fileData)(function(response) {
                document.getElementById('response').innerText = response;
            });
        };
        reader.readAsDataURL(file);
    } else {
        document.getElementById('response').innerText = 'Please choose a file to upload.';
    }
});