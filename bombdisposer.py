# import sys, os
# sys.path.insert(0,'../..')

from math import floor
from random import sample
from time import perf_counter
from dataclasses import dataclass, asdict, field
import threading
import sys
import numpy as np

from sanic import Sanic
from sanic import response
from sanic_session import Session, InMemorySessionInterface

from domonic.html import *
from domonic.CDN import *
from domonic.terminal import say

SIZE = 12 # how many columns and rows
TILE_SIZE = 35 # the pixel size of each grid.
IMAGE = "images/img2.jpg" # the cover image

# if your grid SIZE is bigger than 32 you may need to up the recursion limit
# say(sys.getrecursionlimit())
# sys.setrecursionlimit(5000)

app = Sanic(name='Minesweeper')
app.static('/images', './images')

session = Session(app, interface=InMemorySessionInterface())

ASSETS = {
    'clear': 'images/icons/clear.png',
    'bomb': "images/icons/bomb.png",
    'flag': 'images/icons/flag.png'
}


class Clock(tag):
    def __str__(self):
        return str(div( "&nbsp;", 
        span("00", _id="minutes"),":", span("00", _id="seconds"),
        _style="display:inline-block;" )
    )


@dataclass
class GameData:
    flag_count :int = 0
    mine_count :int = 20
    game_over :bool= False
    game_started :bool = False
    game_timer_start :int = 0
    #tiles = np.array([], dtype ='object')
    mine_tiles : list = field(default_factory=list)
    tiles_checked :list = field(default_factory=list)
    # tile_lookup :object = field(default_factory=object)
    grid : list = field(default_factory=list)


class Game(object):
    """ Bomb Disposer. The data is stored on a session """
    
    js_code = script(_type="text/javascript").html(
        """
        $( document ).ready(function() {
            $('.tile').on('click', function() {
                $.get('/move?tile='+$(this).attr('id'), function(response){
                    $("#gameboard").html($(response).html());
                });
            });
            $( ".tile" ).contextmenu(function(e) {
                e.preventDefault();
                $.get('/flag?tile='+$(this).attr('id'), function(response){
                    $("#gameboard").html($(response).html());
                });
            });
        });
        function change_density(evt){
            $.get('/density?value='+$("#myRange").val(), function(response){
                $("#myRange").html(response);
                // update the bombcount to reflect the game settings
                $("#bomb_count").html( $("#myRange").val() )
            });
        };
        """
    )

    # create a template so can use in requests... see /density
    density_tmpl = lambda val: div(
            input(_type="range", _min="20", _max="100", _value=val, _class="slider", _id="myRange", _style="width:100%;"),
            _class="slidecontainer",
            _onmouseup="change_density()",
            _ontouchend="change_density()"
        )

    def __init__(self, request=None):
        self.state = GameData()
        if request is not None:
            if not request.ctx.session.get('game'):
                request.ctx.session['game'] = asdict(self.state)
            else:
                data = request.ctx.session.get('game')
                self.state.flag_count = data['flag_count']
                self.state.mine_count = data['mine_count']
                self.state.game_over = data['game_over']
                self.state.game_started = data['game_started']
                self.state.game_timer_start = data['game_timer_start']
                self.state.mine_tiles = data['mine_tiles']
                self.state.tiles_checked = data['tiles_checked']
                self.state.grid = data['grid']

        self.tiles = np.array([], dtype='object')
        self.mine_counter_txt = f'{self.state.mine_count:0>3}'
        
        instructions = [h1("💥 Bomb Disposer 💥"),
            details(
                summary("Instructions"),
                p("Uncover all the squares or mark all bombs with a flag to win. The game starts after you click on the first tile.", _style="font-size:12px;"),
                p(b("Left Click:"), "Reveal tile. ", b("Right Click:"), "Add/Remove Flag.", _style="font-size:12px;"),
                sub("hint: When an uncovered tile contains a number, that is how many mines are touching that tile.")
            ),
            a(i('START AGAIN'), _href='/reset'),
            # details(
            #     summary("Settings"),
            #     b("Grid Size:", input(_type="range", _min="0", _max="32", _value="16", _class="slider", _id="myRange") ), 
            #     b("Background image:", select(_type="text"))
            # ),
            h3("💣  Difficulty", div(self.mine_counter_txt, _id="bomb_count")),
            Game.density_tmpl(self.state.mine_count),
            h2('⏱️', Clock()),
            p("Click anywhere on the image to begin:"),
            div(
                h2("🙂" if not self.state.game_over else "😞"), _id="face",
                **{"_aria-label":"I'm not going to help you!"}, **{"_data-balloon-pos":"down"})]

        self.heading = header(*instructions)
        self.cover = IMAGE
        self.grid=[]
        if len(self.state.grid)<1:
            self.init_tiles()
        else:
            self.load_tiles_from_session()

        self.tile_lookup = {}
        for t in self.tiles.flatten():
            self.tile_lookup[t._id] = t


    def update_tiles_state(self):
        """ update the gameboard state """
        self.state.grid = [[asdict(t) for t in row] for row in self.tiles]


    def load_tiles_from_session(self):
        """ loads a grid from an existing game stored in the session """
        self.grid=[]
        self.tiles = np.array([], dtype='object')
        self.tiles.flatten()
        for cc, c in enumerate(self.state.grid):
            row = []
            for cr, r in enumerate(c):
                img = self.cover
                t = Tile(str(img), cc, cr, r)
                self.tiles = np.append(self.tiles, t)
                row.append(t)
            self.grid.append(row)
        self.tiles = self.tiles.reshape([SIZE, SIZE])


    def init_tiles(self):
        """ init a tile grid and tile array """
        grid_layout = []
        for r in range(SIZE):
            row = []
            drow = []
            for c in range(SIZE):
                img = self.cover
                t = Tile(str(img), r, c)
                self.tiles = np.append(self.tiles, t)
                row.append(t)
                drow.append(asdict(t))
            self.grid.append(row)
            self.state.grid.append(drow)
        self.tiles = self.tiles.reshape([SIZE, SIZE])


    def create_mines(self, first_tile):
        """ Set random tiles as mines """
        tiles = list(self.tile_lookup.keys())
        tiles.remove(first_tile) # no lose on the first turn.
        self.state.mine_tiles = sample(tiles, k=self.state.mine_count)
        for mine in self.tiles.flatten():
            if mine._id in self.state.mine_tiles:
                mine.has_mine = True


    def find_neighbours(self):
        """ find neighbour tile props """
        for tile in self.tiles.flatten():
            neighbours, mines = self.find_neighbouring_tiles(tile)
            tile.neighbouring_tiles = [ n._id for n in neighbours]
            tile.neighbouring_mines = mines


    def find_neighbouring_tiles(self, target_tile):
        """ find mine/non-mine neighbours as separate lists """
        neighbours = []  # 8-squares surrounding the target tile"""
        offsets = np.array([(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)])
        the_index = np.array([target_tile.index[0], target_tile.index[1]])
        for offset in offsets:
            try:
                if all(list(map(lambda x: x >= 0, tuple(offset + the_index)))):
                    neighbours.append(self.tiles[tuple(the_index + offset)])
            except IndexError:  # out of bounds
                continue
        
        # count neighbouring mines
        mines = sum(map(lambda x: x.has_mine, neighbours))
        return neighbours, mines


    def update_mine_counter(self):
        """ Update the mine counter text """
        remaining = self.state.mine_count - self.state.flag_count
        self.state.mine_counter_txt = f'{remaining:0>3}'


    def set_mine_density(self, value):
        """ Adjust mine density based on slider """
        self.state.mine_count = int(value)
        self.state.mine_counter_txt = f'{self.state.mine_count:0>3}'


    def toggle_flag(self, tile):
        """ right-click """
        if type(tile) is str:
            tile = self.tile_lookup[tile]

        if any([tile.is_visible, self.state.game_over]):
            return

        if tile.has_flag:
            tile.has_flag = False
            self.state.flag_count -= 1
            self.update_mine_counter()
        else:
            tile.has_flag = True
            self.state.flag_count += 1
            self.update_mine_counter()


    def remove_tiles(self, tile):
        """ on click check tiles """
        if type(tile) is str:
            tile = self.tile_lookup[tile]

        if any([tile.is_visible, self.state.game_over, tile.has_flag, tile._id in self.state.tiles_checked]):
            # say('You already clicked that tile!')
            return

        # add to list of checked tiles
        self.state.tiles_checked.append(tile._id)

        # tile is a mine
        if tile.has_mine:
            say('You died')
            tile.image_path = ASSETS['bomb']
            tile.is_visible = True
            self.state.game_over = True
            self.reveal_mines()
            return "GameOver"  # TODO - user popup to replay?

        elif tile.neighbouring_mines == 0:
            tile.image_path = ASSETS['clear']
            tile.is_visible = True
            # check all neighbours
            # for next_tile in tile.neighbouring_tiles:
            #     self.remove_tiles(next_tile)
            # use threading to check neighbours
            jobs = []
            for next_tile in tile.neighbouring_tiles:
                thread = threading.Thread(target=self.remove_tiles(next_tile))
                thread.setDaemon(True)
                jobs.append(thread)
            map(lambda j: j.start(), jobs)
            map(lambda j: j.join(), jobs)

        else:
            tile.image_path = f'images/numbers/{tile.neighbouring_mines}.png'
            tile.is_visible = True


    def reveal_mines(self):
        """ show mines """ 
        for m in self.state.mine_tiles:
            mine = self.tile_lookup[m]
            # TODO - show correct / incorrect guesses
            # if mine.has_flag:
            #     mine.image_path = ASSETS['bomb']
            #     mine.is_visible = True
            # else:
            mine.image_path = ASSETS['bomb']
            mine.is_visible = True


    def start_game(self, tile):
        """ starts with first click """
        self.state.game_started = True
        self.create_mines(tile)
        self.find_neighbours()
        self.remove_tiles(tile)

    
    def check_winner(self):
        """ if all mines are accounted for and tiles uncovered """
        target = (SIZE*SIZE) - self.state.mine_count
        if not self.state.game_over and len(self.state.tiles_checked) == target:
            self.state.game_over = True
            say('You won!')
            return True
        else:
            return False


@dataclass
class TileData:
    _id :bool = None
    image_path :str = None
    image_flag :str = ASSETS['flag']
    index :list = field(default_factory=list)
    has_mine :bool = False
    is_visible :bool = False
    has_flag :bool = False
    neighbouring_tiles :list = field(default_factory=list)
    neighbouring_mines :int = 0  # count of nearby mines


class Tile(button, TileData, object):
    """ A single tile """

    def __init__(self, image, row, col, data=None):
        self._id=f'tileR{row}C{col}'
        self.image_path = image

        if 'icons' not in self.image_path and 'numbers' not in self.image_path:
            self.__image_tile = div(_style=f"width:100%;height:100%;background:url({self.image_path}); background-position: -{col*TILE_SIZE}px -{row*TILE_SIZE}px;background-size:{TILE_SIZE*SIZE}px {TILE_SIZE*SIZE}px;")
        else:
            self.__image_tile = div(_style=f"width:100%;height:100%;background:url({self.image_path});background-size:{TILE_SIZE}px {TILE_SIZE}px;")

        self.index = [row, col]
        # self.has_flag = False
        self.neighbouring_tiles = []  # list of nearby tiles
        self.neighbouring_mines = 0  # count of nearby mines

        if data is not None:
            self._id = data['_id']
            self.image_path = data['image_path']
            
            if 'icons' not in self.image_path and 'numbers' not in self.image_path:
                self.__image_tile = div(_style=f"width:100%;height:100%;background:url({self.image_path}); background-position: -{col*TILE_SIZE}px -{row*TILE_SIZE}px;background-size:{TILE_SIZE*SIZE}px {TILE_SIZE*SIZE}px;")
            else:
                self.__image_tile = div(_style=f"width:100%;height:100%;background:url({self.image_path});background-size:{TILE_SIZE}px {TILE_SIZE}px;")

            self.index = data['index']
            self.has_mine = data['has_mine']
            self.is_visible = data['is_visible']
            self.has_flag = data['has_flag']
            self.neighbouring_tiles = data['neighbouring_tiles']
            self.neighbouring_mines = data['neighbouring_mines']

        super().__init__(self.image_tile , _src=self.image_path, _id=f'tileR{row}C{col}', _class="tile")
        self.style.padding = '0px'
        self.style.margin = '0px'
        self.style.border = "none"
        # self.style.borderStyle = "solid"
        # self.style.borderColor = "black"
        # self.style.borderWidth = '0.5px'

        self.style.width = str(TILE_SIZE) + "px"
        self.style.height = str(TILE_SIZE) + "px"
        self.style.backgroundColor = "white"

    @property
    def image_tile(self):
        if self.has_flag:
            return div(_style=f"width:100%;height:100%;background:url({self.image_flag});background-size:{TILE_SIZE}px {TILE_SIZE}px;")
        else:
            return self.__image_tile

    # def __str__(self):
        # return str(self)

    def __repr__(self):
        # only used for testing....
        if self.has_mine:
            self.style.backgroundColor = 'red'
            # self += (div("💣"))
        if self.has_flag:
            self.style.backgroundColor = 'blue'
        if self.is_visible:
            self.style.border = 'double'
            self.style.borderColor = 'green'
        return str(self)


@app.route('/reset')
async def reset(request):
    request.ctx.session['game'] = None
    return response.redirect('/')


@app.route('/density') # TODO - change to 'difficulty'?
async def density(request):
    game = Game(request)
    # print(game.state.mine_count)
    if game.state.game_started:
        return response.html(str(Game.density_tmpl(game.state.mine_count)))

    value = request.args['value'][0]
    game.set_mine_density(value)
    request.ctx.session['game'] = asdict(game.state)  # store the game data on the session    
    return response.html(str(Game.density_tmpl(game.state.mine_count)))


@app.route('/flag')
async def flag(request):
    game = Game(request)  # pass request into game so can recover data from the session
    selected_tile = request.args['tile'][0]
    game.toggle_flag(selected_tile)
    game.check_winner()
    game.update_tiles_state()  # update the state of the game
    game.load_tiles_from_session()  # redraw the grid after data updates
    request.ctx.session['game'] = asdict(game.state)  # store the game data on the session
    # render the board
    board = main(game.heading, *[''.join([str(el) for el in row]) for row in game.grid], Game.js_code, _id="gameboard", _style=f"width:{TILE_SIZE*SIZE}px;")
    return response.html(str(board))


@app.route('/move')
async def move(request):
    game = Game(request)  # build the game from the session
    selected_tile = request.args['tile'][0]
    if game.state.game_over and not game.state.game_started:
        request.ctx.session['game'] = None
        return response.redirect('/')
    elif not game.state.game_started:
        game.start_game(selected_tile)
        game.state.game_started = True
    else:
        r = game.remove_tiles(selected_tile)
        if r is not None and "GameOver" in r:
            # return response.html(str("Game Over"))
            print('game over')

    game.check_winner()
    game.update_tiles_state()  # update the state of the game
    game.load_tiles_from_session()  # redraw the grid after data updates
    request.ctx.session['game'] = asdict(game.state)  # update the session
    # render the board
    board = main(game.heading, *[''.join([str(el) for el in row]) for row in game.grid], Game.js_code, _id="gameboard", _style=f"width:{TILE_SIZE*SIZE}px;")
    return response.html(str(board))


@app.route('/')
@app.route('/play')
async def play(request):
    jquery = script(_src="https://code.jquery.com/jquery-3.5.1.min.js")
    request.ctx.session['game'] = None
    game = Game(request)
    request.ctx.session['game'] = asdict(game.state)
    board = main(game.heading, *[''.join([str(el) for el in row]) for row in game.grid], Game.js_code, _id="gameboard", _style=f"width:{TILE_SIZE*SIZE}px;")
    return response.html(str(html(
            head(
                jquery,
                link(_rel="stylesheet", _type="text/css", _href=CDN_CSS.MVP),
                link(_rel="stylesheet", _type="text/css", _href=CDN_CSS.BALLOON)
            ),
            body(
                str(board)
            ))))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000, debug=True)