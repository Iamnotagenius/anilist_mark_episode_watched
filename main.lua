---@class SubprocessResult
---@field stdout string
---@field stderr string
---@field error_string string
---@field status integer
---@field killed_by_us boolean

---@class Result
---@field status string
---@field message string
---@field matches table
---@field page table


local mp = require('mp')
local msg = require('mp.msg')
local utils = require('mp.utils')
local input = require('mp.input')

---@param result SubprocessResult
---@param error string
---@return Result|nil
local function handle_subprocess_result(result, error)
    if error ~= nil then
        mp.osd_message('Failed to run reporter: ' .. error)
        return nil
    elseif result.status ~= 0 then
        mp.osd_message('Reporter failed: ' .. result.error_string)
        msg.error('Reporter error: ' .. result.stderr)
        return nil
    end

    ---@type Result
    return utils.parse_json(result.stdout)
end

---@param args table<string>
---@return Result|nil
local function run_py(args)
    local dir = mp.get_script_directory()
    local env = utils.get_env_list()
    table.insert(env, ('SCRIPT_DIR=%s'):format(dir))
    local result, error = mp.command_native({
        name = 'subprocess',
        args = {
            utils.join_path(dir, '.venv/bin/python'),
            utils.join_path(dir, 'reporter.py'),
            unpack(args),
        },
        env = env,
        capture_stderr = true,
        capture_stdout = true,
        playback_only = false,
    })
    return handle_subprocess_result(result, error)
end

local function report_progress()
    local percent = mp.get_property('time-pos') / mp.get_property('duration')
    if percent < 0.75 then
        return
    end
    local result = run_py({'report', mp.get_property('path')})
    if result ==  nil then
        return
    end
    if result.status == 'error' then
        msg.error(('failed to report progress: %s'):format(result.message))
        return
    elseif result.status == 'tokenupdate' then
        msg.error(('token needs update: %s'):format(result.message))
        return
    end
end

local function search_media()
    local dir = utils.split_path(mp.get_property('path'))
    local info = utils.file_info(utils.join_path(dir, '.anilist.json'))
    if info ~= nil then
        return
    end

    local result = run_py {'guessit', mp.get_property('path')}
    if result == nil then
        return
    end
    local to_id = {}
    input.get {
        prompt = 'Anime search >',
        default_text = result.matches.title,
        complete = function (query)
            mp.osd_message(('Querying %q...'):format(query), 5)
            local search = run_py {'search', query}
            if search == nil then
                return {}, 1
            end
            if search.status == 'error' then
                mp.osd_message(('Error querying anilist: %s'):format(search.message))
                return {}, 1
            end
            local candidates = {}
            to_id = {}
            for _, media in ipairs(search.page) do
                local key = ('%s [%s]'):format(media.title.english, media.title.romaji)
                table.insert(candidates, key)
                to_id[key] = media.id
            end

            return candidates, 1
        end,
        submit = function (choice)
            if to_id[choice] == nil then
                mp.osd_message('Submitted text is not valid. The value must be chosen from complete candidates.', 5)
                return
            end
            local dir = utils.split_path(mp.get_property('path'))
            local media_file, err = io.open(utils.join_path(dir, '.anilist.json'), 'w')
            if media_file == nil then
                mp.osd_message(('Error saving media data: %s'):format(err), 5)
                return
            end

            _, err = media_file:write(utils.format_json({media_id = to_id[choice]}))
            if err ~= nil then
                mp.osd_message(('Error saving media data: %s'):format(err), 5)
                return
            end
            media_file:close()
        end
    }
end

local function auth()
    local result = run_py({'auth'})
    if result == nil then
        return false
    end
    if result.status == 'error' then
        mp.osd_message(('Error occured during token check: %s'):format(result.message))
        return false
    elseif result.status == 'tokenupdate' then
        mp.osd_message(('Access token needs update: %s'):format(result.message), 5)
        input.get {
            prompt = 'Paste access token here:',
            submit = function (token)
                local f, err = io.open(utils.join_path(mp.get_script_directory(), '.anilist.jwt'), 'w')
                if f == nil then
                    mp.osd_message(('Error saving token: %s'):format(err))
                    return
                end
                _, err = f:write(token)
                if err ~= nil then
                    mp.osd_message(('Error saving token: %s'):format(err))
                    return
                end
                f:close()

                -- mp.osd_message('Access token saved')
            end,
            closed = function ()
                mp.command_native({'script-binding', 'search_media'})
            end
        }
        return false
    end
    return true
end

mp.add_hook('on_unload', 50, report_progress)
mp.add_key_binding('ctrl+q', 'search_media', search_media)

local success = auth()
if success then
    mp.register_event('start-file', search_media)
end
