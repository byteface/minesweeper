# Bomb Disposer

The minesweeper game built to test using domonic and sanic.

<img src="https://github.com/byteface/bombdisposer/blob/master/images/bigbomb.png" width="250px" height="auto"/>


##### setup
	python3 -m venv venv
	. venv/bin/activate
	python -m pip install -r requirements.txt


##### running
    python bombdisposer.py


## about

- Test storing game data in a session.

- The python metaclass dumps to a dict. So by using it as the model for all Game assets you can store game state. Here I do it on a session (which a user can see if they probe).

- Decisions on users success are made on the server side aysnc.

- Threads are used to speed-up checking the tiles.

- If you make HUGE grid. Increase recursion limit at the top of the file. i.e

    print(sys.getrecursionlimit())
    sys.setrecursionlimit(5000)

<img src="https://github.com/byteface/bombdisposer/blob/master/images/screenshot.png" width="100%" height="auto" />


## Notes

Still in dev. You may have to comment-out any 'say' commands which i use for testing...

    # from domonic.terminal import say
    # say("something")


## Still todo

- change cover from UI
- change grid size from UI
- timer
- save best times
- sfx
- consider swap out numpy/sanic for something lighter. But not important for now.