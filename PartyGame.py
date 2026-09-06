# pip install flask flask-socketio eventlet

from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
import random
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ---------------- GAME STATE ----------------
game = {
    "players": [],
    "dares": [],
    "used_dares": [],
    "host": None,
    "spinning": False,
    "penalties": {},
    "current": None
}

# ---------------- HOME ----------------
@app.route('/')
def index():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{text-align:center;font-family:sans-serif;background:#f7f8fb;}
.container{max-width:400px;margin:auto;}
.card{background:white;padding:20px;margin:15px;border-radius:12px;}
button{padding:12px;border:none;border-radius:10px;background:#ff6b6b;color:white;width:100%;}
input{padding:12px;width:100%;margin:5px 0;}
</style>
</head>
<body>

<h1>🍻 Drinking Game</h1>

<div class="container">

<div class="card">
<h3>Join Game</h3>
<input id="joinName" placeholder="Your Name">
<button onclick="join()">Join</button>
</div>

<div class="card">
<h3>Host Game</h3>
<input id="hostName" placeholder="Your Name">
<button onclick="host()">Host</button>
</div>

</div>

<script>
function join(){
 location.href="/game?name="+joinName.value;
}

function host(){
 fetch('/host',{
  method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({name:hostName.value})
 }).then(()=>location.href="/game?name="+hostName.value);
}
</script>

</body>
</html>
""")

# ---------------- HOST ----------------
@app.route('/host', methods=['POST'])
def host():
    data = request.json
    game["players"] = [data["name"]]
    game["dares"] = []
    game["used_dares"] = []
    game["host"] = data["name"]
    game["spinning"] = False
    game["penalties"] = {data["name"]: 0}
    return {"status":"ok"}

# ---------------- GAME ----------------
@app.route('/game')
def game_page():
    return render_template_string("""<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{text-align:center;font-family:sans-serif;background:#f7f8fb;}
.player{background:#4dabf7;padding:6px;margin:4px;border-radius:10px;color:white;display:inline-block;}
.host{border:2px solid gold;}
canvas{margin-top:10px;width:100%;max-width:320px;}
button{padding:10px;margin:5px;border:none;border-radius:10px;background:#ff6b6b;color:white;}
.dropdown{margin-top:10px;}
.dare{background:#4dabf7;color:white;padding:6px;margin:4px;border-radius:8px;}
</style>
</head>

<body>

<h2>Game Room</h2>
<div id="players"></div>

<canvas id="wheel" width=300 height=300></canvas><br>
<button id="spinBtn" onclick="spin()">SPIN</button>

<h2 id="result"></h2>

<div id="decision" style="display:none;">
<button onclick="done()">✅ Done</button>
<button onclick="forfeit()">❌ Forfeit</button>
</div>

<hr>

<h3>Your Dares</h3>
<button onclick="toggle()">Toggle</button>
<div id="dropdown" class="dropdown" style="display:none;"></div>

<input id="dare" placeholder="Dare">
<button onclick="addDare()">Add</button>

<hr>

<button onclick="toggleHost()">Host Tools</button>
<div id="hostPanel" style="display:none;"></div>

<script src="https://cdn.socket.io/4.0.1/socket.io.min.js"></script>
<script>
const socket=io();
const params=new URLSearchParams(location.search);
const name=params.get('name');

let allDares=[];
let penalties={};
let usedDares=[];
let currentAngle=0;
let isHost=false;
let pendingResult=null;

// JOIN
socket.emit('join',{name});

socket.on('update',data=>{
 isHost = data.host === name;
 penalties = data.penalties;
 usedDares = data.used_dares || [];
 spinBtn.disabled = false;

 spinBtn.style.display = isHost ? "inline-block" : "none";

 players.innerHTML = data.players.map(p=>
  `<div class="player ${p==data.host?'host':''}">
   ${p} (🍻 ${penalties[p]||0})
   ${isHost && p!==data.host ? `<button onclick="kick('${p}')">X</button>`:''}
  </div>`
 ).join('');

 allDares = data.dares;

 renderMyDares();
 renderHostPanel(data);
 drawWheel(allDares,currentAngle);
});

// SPIN
function spin(){
 if(!isHost) return;
 spinBtn.disabled=true;
 socket.emit('spin');
}

socket.on('spin_result', data=>{
 const slice = 360 / allDares.length;
 const baseSpins = 360 * 6;
 const pointerOffset = 270;

 const targetAngle =
   baseSpins +
   (pointerOffset - (data.index * slice + slice/2));

 animateSpin(currentAngle,currentAngle+targetAngle);
 pendingResult = data;
});

// DECISION
function done(){
 socket.emit('done');
 decision.style.display="none";
}

function forfeit(){
 socket.emit('forfeit');
 decision.style.display="none";
}

// SHOW RESULT WITH TOTAL
socket.on('forfeit_result', data=>{
 result.innerText =
 `${data.player}: ${pendingResult.text} (${data.shots} shots) | Total: ${data.total}`;
});

// DARES
function addDare(){
 socket.emit('add',{text:dare.value,player:name});
 dare.value="";
}

function renderMyDares(){
 const mine = allDares.filter(d=>d.player===name);

 dropdown.innerHTML = mine.map(d=>{
   const idx = allDares.indexOf(d);
   const mark = usedDares.includes(idx) ? "✅" : "🆕";
   return `<div class="dare">${mark} ${d.text}</div>`;
 }).join('');
}

function toggle(){
 dropdown.style.display =
  dropdown.style.display==="none"?"block":"none";
}

// ACTIONS
function kick(p){
 socket.emit('kick',{p});
}

// HOST PANEL
function toggleHost(){
 hostPanel.style.display =
  hostPanel.style.display==="none"?"block":"none";
}

function renderHostPanel(data){
 if(!isHost) return;

 hostPanel.innerHTML = `
 <button onclick="clearDares()">⚠️ Clear All</button>
 ${data.dares.map((d,i)=>
   `<div>${d.text} <button onclick="deleteDare(${i})">❌</button></div>`
 ).join('')}
 `;
}

function deleteDare(i){
 socket.emit('delete_dare',{i});
}

function clearDares(){
 if(confirm("Delete ALL dares?")){
  socket.emit('clear_dares');
 }
}

// ANIMATION
function animateSpin(start,end){
 const duration=4000;
 const startTime=performance.now();

 function frame(time){
   let t=(time-startTime)/duration;
   if(t>1)t=1;

   const ease=1-Math.pow(1-t,4);
   currentAngle=start+(end-start)*ease;

   drawWheel(allDares,currentAngle);

   if(t<1){
     requestAnimationFrame(frame);
   } else {
     currentAngle = end % 360;
     spinBtn.disabled = false;

     if(pendingResult){
       result.innerText =
         `${pendingResult.player}: ${pendingResult.text}`;
       if(isHost) decision.style.display="block";
     }
   }
 }

 requestAnimationFrame(frame);
}

// WHEEL (unchanged)
function drawWheel(dares,rotation=0){
 const canvas=wheel;
 const ctx=canvas.getContext('2d');

 if(dares.length===0) return;

 const angle=2*Math.PI/dares.length;

 ctx.clearRect(0,0,300,300);

 ctx.save();
 ctx.translate(150,150);
 ctx.rotate(rotation*Math.PI/180);

 dares.forEach((d,i)=>{
   ctx.beginPath();
   ctx.moveTo(0,0);
   ctx.arc(0,0,140,i*angle,(i+1)*angle);
   ctx.fillStyle=`hsl(${i*360/dares.length},70%,65%)`;
   ctx.fill();
 });

 ctx.restore();

 ctx.beginPath();
 ctx.moveTo(150,10);
 ctx.lineTo(140,30);
 ctx.lineTo(160,30);
 ctx.fillStyle="#ff6b6b";
 ctx.fill();
}
</script>

</body>
</html>
""")

# ---------------- SOCKET ----------------
@socketio.on('join')
def join(data):
    if data['name'] and data['name'] not in game["players"]:
        game["players"].append(data['name'])
        game["penalties"][data['name']] = 0
    emit('update', game, broadcast=True)

@socketio.on('add')
def add(data):
    game["dares"].append(data)
    emit('update', game, broadcast=True)

@socketio.on('kick')
def kick(data):
    if data['p'] != game["host"]:
        game["players"].remove(data['p'])
        game["penalties"].pop(data['p'], None)
    emit('update', game, broadcast=True)

@socketio.on('delete_dare')
def delete_dare(data):
    if 0 <= data['i'] < len(game["dares"]):
        game["dares"].pop(data['i'])
    emit('update', game, broadcast=True)

@socketio.on('clear_dares')
def clear_dares():
    game["dares"] = []
    game["used_dares"] = []
    game["spinning"] = False
    game["current"] = None

    emit('update', game, broadcast=True)

@socketio.on('spin')
def spin():
    if game["spinning"] or not game["dares"] or not game["players"]:
        return

    game["spinning"] = True

    if len(game["used_dares"]) == len(game["dares"]):
        game["used_dares"] = []

    available = [i for i in range(len(game["dares"])) if i not in game["used_dares"]]
    index = random.choice(available)
    game["used_dares"].append(index)

    player = random.choice(game["players"])
    shots = random.randint(1,4)

    game["current"] = {"player": player, "shots": shots}

    emit('spin_result',{
        "index": index,
        "text": game["dares"][index]['text'],
        "player": player
    }, broadcast=True)

    emit('update', game, broadcast=True)

    socketio.start_background_task(reset_spin)

@socketio.on('forfeit')
def forfeit():
    p = game["current"]["player"]
    s = game["current"]["shots"]

    game["penalties"][p] += s

    emit('forfeit_result',{
        "player": p,
        "shots": s,
        "total": game["penalties"][p]
    }, broadcast=True)

    emit('update', game, broadcast=True)

@socketio.on('done')
def done():
    emit('update', game, broadcast=True)

def reset_spin():
    time.sleep(4)
    game["spinning"] = False

if __name__=='__main__':
    socketio.run(app, host='0.0.0.0', port=5000)