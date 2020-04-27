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

// Window variable
var win = chrome.app.window.getAll()[0];

var p2i_btn = document.getElementById('p2i_btn');

p2i_btn.onclick = init_P2I;

var ratio = window.devicePixelRatio;

var canvas = document.getElementById('canvas');
canvas.width = ratio * window.screen.width;
canvas.height = ratio * window.screen.height;
canvas.style.width = window.screen.width.toString() + "px";
canvas.style.height = window.screen.height.toString() + "px";

draw_calibration_pixels();

function draw_calibration_pixels() {
    
    ctx = canvas.getContext("2d");

    var c_pix_size = 2;
    
    ctx.fillStyle = "red";
    ctx.fillRect(0, 0, c_pix_size, c_pix_size);
    
    ctx.fillStyle = "blue";
    ctx.fillRect(0, canvas.height-c_pix_size, c_pix_size, c_pix_size);
    
    ctx.fillStyle = "white";
    ctx.fillRect(canvas.width-c_pix_size, 0, c_pix_size, c_pix_size);

    ctx.fillStyle = "green";
    ctx.fillRect(canvas.width-c_pix_size, canvas.height-c_pix_size, c_pix_size, c_pix_size);

}


function empty_canvas() {
    context = canvas.getContext('2d');
    context.fillStyle = "white";
    context.fillRect(0, 0, canvas.width, canvas.height);

    context.textAlign = "center";
    context.fillStyle = "black";
    context.font = (15 * ratio).toString() + "px Arial";
    context.fillText("Swipe with 4 fingers to return", canvas.width/2, canvas.height - 20);
}

function clear_canvas() {
    context = canvas.getContext('2d');
    context.clearRect(0,0,canvas.width, canvas.height);
}

function touch_start(e) {
    
    if (e.touches.length > 3) {
        stop_drawing();
    }
}

function mouse_start(e) {
    if (e.button != 0){
        stop_drawing();
    }
}

function stop_drawing() {
    remove_listeners();
    clear_canvas();
    canvas.style.zIndex = "0";
    draw_calibration_pixels();
}

function remove_listeners() {
    canvas.removeEventListener('touchstart', ev_canvas, false);
    canvas.removeEventListener('touchmove', ev_canvas, false);
    canvas.removeEventListener('touchend', ev_canvas, false);
    canvas.removeEventListener('mousedown', ev_canvas, false);
    canvas.removeEventListener('mousemove', ev_canvas, false);
    canvas.removeEventListener('mouseup',   ev_canvas, false);

    canvas.removeEventListener('touchstart', touch_start);
    canvas.removeEventListener('mousedown', mouse_start);
}

// Based on https://dev.opera.com/articles/html5-canvas-painting/example-2.js
function init_P2I () {

    canvas.style.zIndex = "2";
    setFullscreen();

    // Get the 2D canvas context.
    context = canvas.getContext('2d');
    context.lineWidth= (14 * ratio).toString();
    context.strokeStyle="black";
    context.lineCap = 'round';
    context.lineJoin = 'round';

    empty_canvas();

    // Pencil tool instance.
    tool = new tool_pencil();

    // Attach the touchstart, touchend, mousedown, mousemove and mouseup event listeners.
    canvas.addEventListener('touchstart', ev_canvas, false);
    canvas.addEventListener('touchmove', ev_canvas, false);
    canvas.addEventListener('touchend', ev_canvas, false);

    canvas.addEventListener('mousedown', ev_canvas, false);
    canvas.addEventListener('mousemove', ev_canvas, false);
    canvas.addEventListener('mouseup',   ev_canvas, false);

    canvas.addEventListener('touchstart', touch_start);
    canvas.addEventListener('mousedown', mouse_start);
  }

// This painting tool works like a drawing pencil which tracks the mouse 
// movements.
function tool_pencil () {
    var tool = this;
    this.started = false;

    // This is called when you start holding down the mouse button.
    // This starts the pencil drawing.
    this.mousedown = function (ev) {
        empty_canvas();
        context.beginPath();
        context.moveTo(ev._x, ev._y);
        tool.started = true;
    };

    this.touchstart = this.mousedown;

    // This function is called every time you move the mouse. Obviously, it only 
    // draws if the tool.started state is set to true (when you are holding down 
    // the mouse button).
    this.mousemove = function (ev) {
      if (tool.started) {
        context.lineTo(ev._x, ev._y);
        context.stroke();
      }
    };

    this.touchmove = this.mousemove;

    // This is called when you release the mouse button.
    this.mouseup = function (ev) {
      if (tool.started) {
        tool.mousemove(ev);
        tool.started = false;
        empty_canvas();
      }
    };

    this.touchend = this.mouseup;
}

// The general-purpose event handler. This function just determines the mouse 
// position relative to the canvas element.
function ev_canvas (ev) {
    if (ev.layerX || ev.layerX == 0) { // Firefox
        ev._x = ev.layerX * ratio;
        ev._y = ev.layerY * ratio;
    } else if (ev.offsetX || ev.offsetX == 0) { // Opera
        ev._x = ev.offsetX * ratio;
        ev._y = ev.offsetY * ratio;
    } else if (ev.changedTouches || ev.changedTouches.length != 0) { // Chromium OS touches
        ev._x = ev.changedTouches[0].screenX * ratio;
        ev._y = ev.changedTouches[0].screenY * ratio;
    }

    // Call the event handler of the tool.
    var func = tool[ev.type];
    if (func) {
        func(ev);
    }
}

function setFullscreen(){
    // Set window to full screen if it is not already
    if (!win.isFullscreen()) {
        win.fullscreen();
    }
}