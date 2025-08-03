# Report your progress to Anilist!
This simple MPV plugin will help you to easily
report progress of shows you watch as well as rate them.

## Setup
First, go to your mpv scripts directory
(on linux it is usually `~/.config/mpv/scripts`)
and then run `git clone https://github.com/Iamnotagenius/anilist_mark_episode_watched.git`.

Then, go to the plugin's directory and make python work:
```
cd anilist_mark_episode_watched
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

And you're good to go! MPV will ask you for access token during the next launch.

## Configuration
Example config, should be placed under `~/.config/mpv/script-opts/anilist_mark_episode_watched.conf`:
```conf
mark_threshold = 0.75 # a value from 0 to 1, where 0 is the beginning of an episode, 1 is the end. From which point episode is considered 'watched'
affected_dir = ~/Videos/Anime # directory where animes are stored
```
You can also change the key bindings in input.conf:
```
<key> script-binding set-anilist-score
<key> script-binding browse-anilist
```

## Usage
On start, the script checks whether it has your access token and if it is valid.
If not, it will open a browser tab where you can get the token.

Then, it will check for a media file in a directory where episodes are stored.
If a media file does not exist, then MPV will prompt you to enter what anime the
directory corresponds to. Once submitted, anime's media id will be stored in its
directory and will be used for setting score and updating progress.

If you want to change media id, you can run `script-message anilist-change-media`
and MPV will prompt you to submit an anime entry again.

You can press `R` to set score for the anime you're currently watching, this will use
10 point format.

You can press `B` to open anime's Anilist page in your browser.

On close, this script determines whether you watch a file in `affected_dir`
and whether you passed `mark_threshold` and if you do,
it marks the current episode as watched.
