/*
Copyright (c) 2019, OptoFidelity OY

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
    2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
    3. All advertising materials mentioning features or use of this software must display the following acknowledgement: This product includes software developed by the OptoFidelity OY.
    4. Neither the name of the OptoFidelity OY nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/

// Prevent long presses to wake up menus etc.
window.oncontextmenu = function(event) {
    event.preventDefault();
    event.stopPropagation();
    return false;
}

// Global variable for GUI window
var win = chrome.app.window.getAll()[0];

// Set initial values
var color = "black";
var connection = "Lost"
var measure = false;

// Get app name and version from manifest.json
var manifest = chrome.runtime.getManifest();
document.getElementById('ver').innerHTML = manifest.version;
document.getElementById('app_name').innerHTML = manifest.name;
document.getElementById('resolution').innerHTML = screen.width+"x"+screen.height;
document.getElementById('resolution2').innerHTML = screen.width+"x"+screen.height;

// Initialize DOM content to match initial values
document.body.style.backgroundColor = color;
document.getElementById('latency').style.backgroundcolor = color;
document.getElementById('time').innerHTML = "";
document.getElementById('connection').innerHTML = connection;

// Give functions to button clicks
document.getElementById('testing_btn').onclick = function () {
    startTesting();
}
document.getElementById('latency_btn').onclick = function () {
    startLatency();
}
document.getElementById('about_btn').onclick = function () {
    showAbout();
}
document.getElementById('exit_btn').onclick = function () {
    exit();
}

// Continuously check ip and port to be valid
document.getElementsByName('ip')[0].addEventListener("input", ipInput);
function ipInput() {
    checkIp(document.getElementsByName('ip')[0]);
}

document.getElementsByName('port')[0].addEventListener("input", portInput);
function portInput(){
    checkPort(document.getElementsByName('port')[0]);
}

// Listen to touches after page has been loaded
window.addEventListener('load', pageLoad)

function pageLoad(){
    // Listener for messages from background.js
    chrome.runtime.onMessage.addListener(messageReceived);

    win.onClosed.addListener(windowClosed);

    document.body.addEventListener('touchstart', touchStart);

    document.body.addEventListener('touchend', touchEnd);
}

function touchStart(e){
    // When touch starts, flash the white rectangle at upper right corner
    document.getElementById('latency').style.backgroundColor="#FFF";

    // If at least 4 touches registered, stop measuring
    /*if (e.touches.length > 3 && measure) {
        stopMeasure();
    }*/
}

function touchEnd(e){
    // When touch ends, change corner rectangle color back to black
    document.getElementById('latency').style.backgroundColor="#000";

    if (measure) {
        stopMeasure();
    }

}


function windowClosed() {
    win.onClosed.removeListener(windowClosed);
    chrome.runtime.onMessage.removeListener(messageReceived);

    document.getElementsByName('ip')[0].removeEventListener(ipInput);
    document.getElementsByName('port')[0].removeEventListener(portInput);
    document.body.removeEventListener('touchstart', touchStart)
    document.body.removeEventListener('touchend', touchEnd)

}

// Handle messages received from background.js
function messageReceived(msg) {
    // Split message at first colon
    var data = msg.split(/:(.+)/)[1];

    if (msg.startsWith("conn:")) {
        // If message is connection message, check if connection established or broken and update view
        if (data === "True") {
            connection = "OK";
        }
        else if (data === "False"){
            connection = "Lost"
        }
        else {
            connection = data;
        }
        document.getElementById('connection').innerHTML = connection;
    }
    else if (msg === "stop") {
        connection = "Lost";
        document.getElementById('connection').innerHTML = connection;
        return;
    }
    else if (msg === "reload") {
        // With command "reload" app can be booted
        chrome.runtime.sendMessage(msg);
    }
    else if (msg === "device_conn") {
        // If python script is connected, enable buttons
        setButtonState(true);
        document.getElementById('errors').innerHTML = 'Backend connected';
        setTimeout(function() {
            document.getElementById('errors').innerHTML = '<br/>';
        }, 2000);
    }
    else if (msg === "device_disconn") {
        // If python script is not connected, disable buttons and stop measuring
        setButtonState(false);
        document.getElementById('errors').innerHTML = 'Launch Python test script';
        showConfigurator();
    }
    else if (msg.startsWith("config:")) {
        // If new configuration comes from python script, set it to fields
        var conf = JSON.parse(data);
        setConfig(conf);
    }
    
    // All messages except stop updates timestamp on the page
    document.getElementById('time').innerHTML = Date.now();
}

function setConfig(conf) {
    document.getElementsByName('ip')[0].value = conf.ip;
    document.getElementsByName('port')[0].value = parseInt(conf.port);
    
    var devlist = document.getElementById('devpaths');
    var ind = 0;
    var correct_ind = 0;

    for (i= devlist.options.length - 1; i>=0 ;  i--){
        devlist.options.remove(i);
    }

    conf.devpaths.forEach(function(path) {
        if (path === conf.devpath){
            correct_ind = ind;
        } else {
            ind++;
        }
        var newopt = document.createElement("option");
        newopt.text = path;
        devlist.options.add(newopt);
    });

    devlist.selectedIndex = correct_ind;

    // Update input fields appearance
    checkIp(document.getElementsByName('ip')[0]);
    checkPort(document.getElementsByName('port')[0]);
}

// Function to validate ip address
// http://www.w3resource.com/javascript/form/ip-address-validation.php
function validateIP(ipaddress) {  
        if (/^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/.test(ipaddress))
        {  
            return (true)
        }  
    return (false)  
}

// Function to validate port number
function validatePort(port) {
    // port = parseInt(port);
    if (0 < port && port < 65535){
        return (true);
    }
    return (false);
}

function checkIp(elem) {
    updateInputBorder(elem, validateIP(elem.value));
}

function checkPort(elem) {
    updateInputBorder(elem, validatePort(parseInt(elem.value)));
}

function updateInputBorder(elem, valid) {
    if (typeof(elem.style) != 'undefined') {
        if (valid) {
            elem.style.borderColor = "white";
            elem.style.boxShadow = "none";
        } else {
            elem.style.borderColor = "red";
            elem.style.boxShadow = "0 0 10px 2px red";   
        }
    }
}

// Function to start touch testing
function startTesting() {

    // Get values from the form and check resolution
    var obj = {};
    obj.ip = document.getElementsByName('ip')[0].value;
    obj.port = document.getElementsByName('port')[0].value;
    obj.screen_height = window.screen.availHeight;
    obj.screen_width = window.screen.availWidth;

    var dev_elem = document.getElementById('devpaths')
    obj.device_path = dev_elem.options[dev_elem.selectedIndex].text;

    // Validate ip and port
    if (!validateIP(obj.ip)){
        document.getElementById('errors').innerHTML = 'Check IP';
        setTimeout(function(){
            document.getElementById('errors').innerHTML = '<br/>';
        }, 2000);
        return;
    }

    if (!validatePort(obj.port)) {
        document.getElementById('errors').innerHTML = 'Check port';
        setTimeout(function(){
            document.getElementById('errors').innerHTML = '<br/>';
        }, 2000);
        return;
    }

    // Hide configurator and show measurement info

    setTimeout(function(){
        measure = true;
    }, 3000);

    setFullscreen();
    hideConfigurator();
    document.getElementById('measurement').style.display = "block";
    document.getElementById('info').style.display = "block";
    document.getElementById('latency').style.display= "none";

    var msg="config:" + JSON.stringify(obj);
    chrome.runtime.sendMessage(msg, function(response) {});

}

function startLatency() {
    // Start latency measurement
    setTimeout(function(){
        measure = true;
    }, 3000);
    setFullscreen();
    hideConfigurator();
    document.getElementById('measurement').style.display = "block";
    document.getElementById('latency').style.display= "block";
    document.getElementById('info').style.display = "none";
    chrome.runtime.sendMessage('latency', function(response) {});
}

function stopMeasure() {
    // Stop measurements, show configuration window
    measure = false;
    showConfigurator();
    chrome.runtime.sendMessage('pause', function(response) {});
}

function showConfigurator() {
    // Show configuration elements
    document.getElementById('configuration').style.display = "block";
    document.getElementById('optofidelity').style.display = "block";
    document.getElementById('measurement').style.display = "none";
    document.getElementById('latency').style.display = "none";
    document.getElementById('about').style.display = "none";
    document.getElementById('canvas').style.display="block";
}

function hideConfigurator() {
    // Hide configuration elements
    document.getElementById('configuration').style.display = "none";
    document.getElementById('optofidelity').style.display = "none";
    document.getElementById('canvas').style.display="none";
}

function setButtonState(state){
    // document.getElementById('latency_btn').disabled = !state;
    document.getElementById('testing_btn').disabled = !state;
}

function setFullscreen(){
    // Set window to full screen if it is not already
    if (!win.isFullscreen()) {
        win.fullscreen();
    }
}

function showAbout() {
    // Show About-elements, hide configuration
    document.getElementById('about_btn').onclick = hideAbout;
    document.getElementById('about_btn').innerHTML = 'Go Back';

    document.getElementById('configuration').style.display = "none";
    document.getElementById('about').style.display = "block";
}

function hideAbout() {
    // Hide About-elements, show configuration
    document.getElementById('about_btn').onclick = showAbout;
    document.getElementById('about_btn').innerHTML = 'About';

    document.getElementById('configuration').style.display = "block";
    document.getElementById('about').style.display = "none";
}

function exit(){
    // Disable measurement button and send stopping message to background
    setButtonState(false);
    chrome.runtime.sendMessage('stop');
}