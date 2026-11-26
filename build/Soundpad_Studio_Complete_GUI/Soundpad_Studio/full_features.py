# Full feature integration layer. Procedural Tkinter only; no custom classes.
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import editing as ed
import projects as pj
import beats as bt
import synth as sy
import render as rnd
import audio_io as aio
import auth as au
from vizualiser import ascii_waveform, ascii_spectrum

EFFECT_DEFAULTS = {
    'gain': (1.0, None), 'fade_in': (1.0, None), 'fade_out': (1.0, None),
    'reverse': (None, None), 'speed': (1.0, None), 'normalize': (.95, None),
    'echo': (.3, .5), 'lowpass': (5000, None), 'highpass': (200, None),
    'distortion': (5, None)
}

def ask_value(title, prompt, initial=None, kind='str', minimum=None, maximum=None):
    if kind == 'int': return simpledialog.askinteger(title, prompt, initialvalue=initial, minvalue=minimum, maxvalue=maximum, parent=STATE['root'])
    if kind == 'float': return simpledialog.askfloat(title, prompt, initialvalue=initial, minvalue=minimum, maxvalue=maximum, parent=STATE['root'])
    return simpledialog.askstring(title, prompt, initialvalue=initial, parent=STATE['root'])

def run_action(fn, *args, refresh=None, **kwargs):
    result = safe_call(fn, *args, **kwargs)
    if refresh and result is not None: refresh()
    return result

def show_track_tools(track):
    tid = track['track_id']
    choice = simpledialog.askstring('Track controls',
        'Track: %s\nEnter: volume / pan / mute / solo / rename / delete' % track['track_name'],
        initialvalue='volume', parent=STATE['root'])
    if not choice: return
    choice = choice.strip().lower()
    if choice == 'volume':
        v = ask_value('Volume', 'Track volume (0–4):', float(track['volume']), 'float', 0, 4)
        if v is not None: run_action(pj.set_track_volume, tid, v, refresh=show_project)
    elif choice == 'pan':
        v = ask_value('Pan', 'Pan (-1 left to +1 right):', float(track['pan']), 'float', -1, 1)
        if v is not None: run_action(pj.set_track_pan, tid, v, refresh=show_project)
    elif choice == 'mute': run_action(pj.toggle_mute, tid, refresh=show_project)
    elif choice == 'solo': run_action(pj.toggle_solo, tid, refresh=show_project)
    elif choice == 'rename':
        n = ask_value('Rename track', 'New track name:', track['track_name'])
        if n: run_action(pj.rename_track, tid, n, refresh=show_project)
    elif choice == 'delete':
        if messagebox.askyesno('Delete track', 'Delete this track and all its content?'):
            run_action(pj.delete_track, tid, refresh=show_project)

def add_full_clip(track):
    files = safe_call(aio.list_user_files, STATE['user']['user_id']) or []
    if not files:
        messagebox.showinfo('Audio library', 'Import WAV files in the Library first.'); return
    opts = '\n'.join('%s — ID %s' % (x['file_name'], x['file_id']) for x in files)
    fid = ask_value('Choose audio', 'Enter library file ID:\n' + opts, files[0]['file_id'], 'int', 1)
    if fid is None: return
    start = ask_value('Timeline position', 'Start time (seconds):', 0.0, 'float', 0)
    trim_s = ask_value('Trim start', 'Trim from beginning (seconds):', 0.0, 'float', 0)
    trim_e = ask_value('Trim end', 'Trim end (blank is not supported here; use 0 for full file):', 0.0, 'float', 0)
    vol = ask_value('Clip volume', 'Volume:', 1.0, 'float', 0, 5)
    fin = ask_value('Fade in', 'Fade-in seconds:', 0.0, 'float', 0)
    fout = ask_value('Fade out', 'Fade-out seconds:', 0.0, 'float', 0)
    if None in (start, trim_s, trim_e, vol, fin, fout): return
    result = safe_call(pj.add_clip, track['track_id'], STATE['user']['user_id'], fid, start, trim_s, trim_e or None, vol, fin, fout)
    if result: set_status(result[1]); show_project()

def manage_clips(track):
    clips = safe_call(pj.list_clips, track['track_id']) or []
    if not clips: messagebox.showinfo('Clips', 'This audio track has no clips.'); return
    clip = next((c for c in clips if c['clip_id'] == ask_value('Select clip', 'Enter clip ID:\n' + '\n'.join('#%s  %s @ %.2fs' % (c['clip_id'], c['file_name'], float(c['start_time'])) for c in clips), clips[0]['clip_id'], 'int')), None)
    if not clip: return
    action = ask_value('Clip editor', 'Action: start / trim_start / trim_end / volume / fade_in / fade_out / delete / effects', 'start')
    if not action: return
    action = action.lower()
    fields = {'start':'start_time','trim_start':'trim_start','trim_end':'trim_end','volume':'volume','fade_in':'fade_in','fade_out':'fade_out'}
    if action == 'delete':
        if messagebox.askyesno('Delete clip', 'Delete selected clip?'): safe_call(pj.delete_clip, clip['clip_id']); show_project()
    elif action in fields:
        value = ask_value('Edit clip', 'New value:', float(clip[fields[action]] or 0), 'float', 0)
        if value is not None:
            kwargs = {fields[action]: value if action != 'trim_end' or value else None}
            safe_call(pj.update_clip, clip['clip_id'], **kwargs); show_project()
    elif action == 'effects': manage_effects(clip)

def manage_effects(clip):
    effects = safe_call(pj.list_effects) or []
    current = safe_call(pj.list_clip_effects, clip['clip_id']) or []
    menu = '\n'.join('%s — %s' % (e['effect_name'], e['description']) for e in effects)
    action = ask_value('Clip effects', 'Current: ' + ', '.join(x['effect_name'] for x in current) + '\n\nEnter effect name to add, or REMOVE:', 'gain')
    if not action: return
    if action.upper() == 'REMOVE':
        ce = ask_value('Remove effect', 'Effect row ID:\n' + '\n'.join('#%s %s' % (x['ce_id'],x['effect_name']) for x in current), None, 'int', 1)
        if ce: safe_call(pj.remove_clip_effect, ce)
    else:
        name = action.lower()
        if name not in [e['effect_name'] for e in effects]:
            messagebox.showwarning('Effect', 'Unknown effect. Available: ' + ', '.join(e['effect_name'] for e in effects)); return
        d1,d2 = EFFECT_DEFAULTS.get(name,(None,None))
        p1 = ask_value(name, 'Parameter 1 (leave blank for default):', d1, 'float') if d1 is not None else None
        p2 = ask_value(name, 'Parameter 2 (leave blank for default):', d2, 'float') if d2 is not None else None
        safe_call(pj.add_clip_effect, clip['clip_id'], name, p1, p2)
    show_project()

def beat_workspace(track, project):
    patterns = safe_call(bt.list_patterns, track['track_id']) or []
    prompt = 'Beat patterns:\n' + ('\n'.join('#%s %s — %s steps, swing %.2f, x%s' % (p['pattern_id'],p['pattern_name'],p['total_steps'],float(p['swing']),p['repeats']) for p in patterns) or '(none)')
    act = ask_value('Beat maker', prompt + '\n\nType NEW, EDIT, DELETE, CUSTOM DRUM:', 'NEW')
    if not act: return
    if act.upper() == 'NEW':
        name = ask_value('New pattern','Pattern name:','Groove')
        steps = ask_value('Steps','Choose 8, 16, 24 or 32:',16,'int',8,32)
        swing = ask_value('Swing','Swing 0–1:',0.0,'float',0,1)
        reps = ask_value('Repeats','Pattern repeats:',4,'int',1,64)
        if None in (steps,swing,reps) or not name: return
        pid,msg = safe_call(bt.create_pattern,track['track_id'],name,steps,swing,reps) or (None,'Could not create pattern')
        if pid:
            preset = ask_value('Preset','Optional preset: ' + ', '.join(bt.list_presets()) + '\nLeave blank for empty pattern:','')
            if preset: safe_call(bt.apply_preset,pid,preset.lower())
            edit_pattern_grid(pid)
    elif act.upper() == 'EDIT':
        pid = ask_value('Edit pattern','Pattern ID:',patterns[0]['pattern_id'] if patterns else None,'int',1)
        if pid and any(p['pattern_id']==pid for p in patterns): edit_pattern_grid(pid)
    elif act.upper() == 'DELETE':
        pid = ask_value('Delete pattern','Pattern ID:',None,'int',1)
        if pid and messagebox.askyesno('Delete pattern','Delete pattern %s?'%pid): safe_call(bt.delete_pattern,pid)
    elif act.upper() in ('RANDOMIZE','SWING','REPEATS','CLEAR','PREVIEW'):
        pid = ask_value('Pattern action','Pattern ID:',patterns[0]['pattern_id'] if patterns else None,'int',1)
        if not pid or not any(p['pattern_id']==pid for p in patterns): return
        if act.upper()=='RANDOMIZE':
            density=ask_value('Randomize','Hit density (0–1):',0.25,'float',0,1)
            if density is not None: safe_call(bt.randomize_pattern,pid,density)
        elif act.upper()=='SWING':
            value=ask_value('Swing','Swing (0–1):',0.0,'float',0,1)
            if value is not None: safe_call(bt.set_swing,pid,value)
        elif act.upper()=='REPEATS':
            value=ask_value('Repeats','Repeat count (1–64):',4,'int',1,64)
            if value is not None: safe_call(bt.set_repeats,pid,value)
        elif act.upper()=='CLEAR':
            if messagebox.askyesno('Clear pattern','Remove every hit in this pattern?'): safe_call(bt.clear_pattern,pid)
        elif act.upper()=='PREVIEW':
            try: safe_call(aio.play_audio,ed.limit(ed.loop_audio(bt.render_pattern(pid,project['bpm'],project['sample_rate']),2)))
            except Exception as exc: messagebox.showerror('Preview failed',str(exc))
    elif act.upper() == 'CUSTOM DRUM':
        files = safe_call(aio.list_user_files,STATE['user']['user_id']) or []
        if not files: messagebox.showinfo('Custom drum','Import a WAV first.'); return
        name=ask_value('Custom drum','Drum name:','Custom hit'); cat=ask_value('Category','kick/snare/hihat/clap/tom/perc/other','other')
        fid=ask_value('Audio file','File ID:\n'+'\n'.join('%s: %s'%(f['file_id'],f['file_name']) for f in files),files[0]['file_id'],'int',1)
        if name and cat and fid: safe_call(bt.add_custom_drum,name,cat.lower(),fid)

def edit_pattern_grid(pid):
    pat = safe_call(bt.get_pattern,pid)
    if not pat: return
    samples = safe_call(bt.list_drum_samples) or []
    if not samples: messagebox.showwarning('Drums','No drum samples are configured. Run setup_db.py.'); return
    win = tk.Toplevel(STATE['root']); win.title('Step sequencer — '+pat['pattern_name']); win.configure(bg=COL['bg']); win.geometry('980x540')
    tk.Label(win,text='STEP SEQUENCER  /  '+pat['pattern_name'],bg=COL['bg'],fg=COL['cyan'],font=('Segoe UI',18,'bold')).pack(anchor='w',padx=20,pady=15)
    grid=tk.Frame(win,bg=COL['bg']); grid.pack(fill='both',expand=True,padx=16,pady=8)
    active={(x['sample_id'],x['step_no']) for x in (safe_call(bt.get_steps,pid) or [])}
    for col in range(pat['total_steps']): tk.Label(grid,text=str(col+1),bg=COL['bg'],fg=COL['muted'],width=3).grid(row=0,column=col+1,padx=1)
    for r,sample in enumerate(samples,1):
        tk.Label(grid,text=sample['name'],bg=COL['bg'],fg=COL['text'],width=16,anchor='w').grid(row=r,column=0,sticky='w')
        for step in range(pat['total_steps']):
            var=tk.BooleanVar(value=(sample['sample_id'],step) in active)
            def toggle(sid=sample['sample_id'],st=step,v=var):
                if v.get(): safe_call(bt.set_step,pid,sid,st,100)
                else: safe_call(bt.clear_step,pid,sid,st)
            tk.Checkbutton(grid,variable=var,command=toggle,bg=COL['bg'],activebackground=COL['bg'],selectcolor=COL['panel2'],fg=COL['cyan']).grid(row=r,column=step+1,padx=1,pady=4)
    foot=tk.Frame(win,bg=COL['bg']); foot.pack(fill='x',padx=20,pady=12)
    button(foot,'CLEAR PATTERN',lambda:(safe_call(bt.clear_pattern,pid),win.destroy()),False).pack(side='left')
    button(foot,'SAVE & CLOSE',win.destroy,True).pack(side='right')

def composer_workspace(track, project):
    instruments = safe_call(sy.list_instruments) or []
    if not instruments: messagebox.showwarning('Composer','No instruments found. Run setup_db.py.'); return
    listing='\n'.join('#%s %s'%(i['instrument_id'],i['name']) for i in instruments)
    ins=ask_value('Instrument','Choose instrument ID:\n'+listing,instruments[0]['instrument_id'],'int',1)
    if not ins:return
    act=ask_value('Composer','Action: NOTE / CHORD / PROGRESSION / BASS / ARPEGGIO / RANDOM / TRANSPOSE / DELETE NOTE / CLEAR / LIST / PIANO ROLL / PLAY TRACK / PREVIEW NOTE', 'NOTE')
    if not act:return
    act=act.upper(); root=ask_value('Root note','Root note (e.g. C4):','C4')
    try: midi=sy.note_to_midi(root or 'C4')
    except ValueError as e: messagebox.showerror('Note',str(e)); return
    start=0.0
    if act=='NOTE':
        note=ask_value('Add note','Note name:', 'C4'); beat=ask_value('Start beat','Start beat:',0.0,'float',0); length=ask_value('Length','Length in beats:',1.0,'float',0.01); vel=ask_value('Velocity','Velocity 1–127:',100,'int',1,127)
        try: n=sy.note_to_midi(note)
        except ValueError as e: messagebox.showerror('Note',str(e)); return
        if None not in (beat,length,vel): safe_call(sy.add_note,track['track_id'],ins,n,beat,length,vel)
    elif act=='CHORD':
        c=ask_value('Chord','Type: '+', '.join(sy.CHORDS.keys()),'major'); beat=ask_value('Start beat','Start beat:',0.0,'float',0); length=ask_value('Length','Length beats:',4.0,'float',.01)
        if c in sy.CHORDS and beat is not None and length: safe_call(sy.add_chord,track['track_id'],ins,midi,c,beat,length)
    elif act in ('PROGRESSION','BASS'):
        p=ask_value('Progression','Name: '+', '.join(sy.PROGRESSIONS.keys()),'pop'); beat=ask_value('Start beat','Start beat:',0.0,'float',0); reps=ask_value('Repeats','Repeats:',1,'int',1,32)
        if p in sy.PROGRESSIONS and beat is not None and reps:
            fn=sy.add_progression if act=='PROGRESSION' else sy.add_bass_line; safe_call(fn,track['track_id'],ins,midi,p,beat,4.0,reps)
    elif act=='ARPEGGIO':
        c=ask_value('Chord','Chord type: '+', '.join(sy.CHORDS.keys()),'minor'); total=ask_value('Duration','Total beats:',8.0,'float',.5); pattern=ask_value('Pattern','up / down / updown','up')
        if c in sy.CHORDS and total: safe_call(sy.add_arpeggio,track['track_id'],ins,midi,c,0,total,.5,pattern)
    elif act=='RANDOM':
        scale=ask_value('Scale','Scale: '+', '.join(sy.SCALES.keys()),'minor_pentatonic'); bars=ask_value('Bars','Number of bars:',4,'int',1,64)
        if scale in sy.SCALES and bars: safe_call(sy.random_melody,track['track_id'],ins,midi,scale,0,bars)
    elif act=='TRANSPOSE':
        sem=ask_value('Transpose','Semitones (+/-):',1,'int',-24,24)
        if sem is not None: safe_call(sy.transpose_track,track['track_id'],sem)
    elif act=='DELETE NOTE':
        notes=safe_call(sy.list_notes,track['track_id']) or []; nid=ask_value('Delete note','Note ID:\n'+'\n'.join('#%s %s beat %.2f'%(n['note_id'],sy.midi_to_name(n['midi_number']),float(n['start_beat'])) for n in notes),None,'int',1)
        if nid: safe_call(sy.delete_note,nid)
    elif act=='CLEAR':
        if messagebox.askyesno('Clear notes','Remove all notes from this instrument track?'): safe_call(sy.clear_notes,track['track_id'])
    elif act=='LIST':
        notes=safe_call(sy.list_notes,track['track_id']) or []
        messagebox.showinfo('Composer notes','\n'.join('#%s %-5s beat %.2f len %.2f vel %s'%(n['note_id'],sy.midi_to_name(n['midi_number']),float(n['start_beat']),float(n['length_beats']),n['velocity']) for n in notes) or 'No notes yet.')
    elif act=='PIANO ROLL':
        notes=safe_call(sy.list_notes,track['track_id']) or []
        messagebox.showinfo('Piano roll','\n'.join('%-5s | beat %-6s | length %s'%(sy.midi_to_name(n['midi_number']),n['start_beat'],n['length_beats']) for n in notes) or 'No notes yet.')
    elif act=='PLAY TRACK':
        try:
            audio=sy.render_instrument_track(track['track_id'],project['bpm'],project['sample_rate'])
            if audio: safe_call(aio.play_audio,ed.limit(ed.normalize(audio,.9)))
            else: messagebox.showinfo('Composer','No notes to play yet.')
        except Exception as exc: messagebox.showerror('Playback failed',str(exc))
    elif act=='PREVIEW NOTE':
        note=ask_value('Preview','Note to preview:','C4')
        if note: safe_call(sy.preview_note,ins,note,1.0,project['sample_rate'])
    notes=safe_call(sy.list_notes,track['track_id']) or []
    messagebox.showinfo('Piano roll','Notes on track:\n'+('\n'.join('#%s  %-5s beat %-6s len %s'%(n['note_id'],sy.midi_to_name(n['midi_number']),n['start_beat'],n['length_beats']) for n in notes[-30:]) or 'No notes yet.'))

def audio_lab():
    files=safe_call(aio.list_user_files,STATE['user']['user_id']) or []
    if not files: messagebox.showinfo('Audio Lab','Import a WAV file first.'); return
    fid=ask_value('Audio Lab','Choose file ID:\n'+'\n'.join('#%s %s'%(f['file_id'],f['file_name']) for f in files),files[0]['file_id'],'int',1)
    if not fid:return
    audio=safe_call(aio.load_audio_by_id,fid,STATE['user']['user_id'])
    if not audio:return
    state={'audio':audio,'undo':[],'redo':[],'saved':True,'name':next((f['file_name'] for f in files if f['file_id']==fid),'audio.wav')}
    ops=['play','waveform','spectrum','analyse','trim','cut','volume','fade in','fade out','reverse','speed','normalize','echo','lowpass','highpass','distortion','loop','insert silence','merge after','mix over','mono','stereo','undo','redo','save']
    while True:
        a=state['audio']; info='%.2fs  |  %s Hz  |  %s ch  |  peak %.1f dB'%(ed.duration(a),a['rate'],len(a['channels']),ed.to_db(ed.get_peak(a)))
        act=ask_value('Audio Lab',info+'\n\nOperation:\n'+', '.join(ops)+'\nEnter BACK to exit:', 'analyse')
        if not act or act.lower()=='back': break
        act=act.lower()
        if act=='play': safe_call(aio.play_audio,ed.limit(a),False); continue
        if act=='waveform': messagebox.showinfo('Waveform',ascii_waveform(a)); continue
        if act=='spectrum': messagebox.showinfo('Spectrum',ascii_spectrum(a)); continue
        if act=='analyse':
            messagebox.showinfo('Analysis','Duration: %.3f sec\nSample rate: %s Hz\nChannels: %s\nPeak: %.2f dB\nRMS: %.2f dB\nClipping: %s'%(ed.duration(a),a['rate'],len(a['channels']),ed.to_db(ed.get_peak(a)),ed.to_db(ed.get_rms(a)),'YES' if ed.is_clipping(a) else 'No')); continue
        if act=='undo' and state['undo']: state['redo'].append(a); state['audio']=state['undo'].pop(); state['saved']=False; continue
        if act=='redo' and state['redo']: state['undo'].append(a); state['audio']=state['redo'].pop(); state['saved']=False; continue
        if act=='save':
            path=filedialog.asksaveasfilename(parent=STATE['root'],defaultextension='.wav',filetypes=[('WAV','*.wav')],initialfile='edited_'+os.path.basename(state['name']))
            if path:
                try: aio.save_wav(path,ed.limit(a)); result=safe_call(aio.import_audio_file,STATE['user']['user_id'],path); messagebox.showinfo('Saved',result[1] if result else 'Saved to '+path); state['saved']=True
                except Exception as exc: messagebox.showerror('Save failed',str(exc))
            continue
        params={}
        if act in ('trim','cut'):
            s=ask_value(act,'Start seconds:',0.0,'float',0); e=ask_value(act,'End seconds:',ed.duration(a),'float',0)
            if None in (s,e) or e<=s: continue
            fn=ed.trim if act=='trim' else ed.cut_out; args=(a,s,e)
        elif act in ('volume','fade in','fade out','speed','normalize','loop','insert silence','lowpass','highpass','distortion'):
            specs={'volume':('Factor:',1.2,'float',0,10),'fade in':('Seconds:',1.0,'float',0,None),'fade out':('Seconds:',1.0,'float',0,None),'speed':('Factor:',1.0,'float',.1,8),'normalize':('Peak:',.95,'float',.01,1),'loop':('Repeats:',2,'int',1,50),'insert silence':('Silence seconds:',1.0,'float',.01,None),'lowpass':('Cutoff Hz:',3000,'float',20,a['rate']/2-1),'highpass':('Cutoff Hz:',300,'float',20,a['rate']/2-1),'distortion':('Amount:',5.0,'float',1,30)}
            label_,default,kind,lo,hi=specs[act]; v=ask_value(act,label_,default,kind,lo,hi)
            if v is None: continue
            if act=='volume': fn,args=ed.change_volume,(a,v)
            elif act=='fade in': fn,args=ed.fade_in,(a,v)
            elif act=='fade out': fn,args=ed.fade_out,(a,v)
            elif act=='speed': fn,args=ed.change_speed,(a,v)
            elif act=='normalize': fn,args=ed.normalize,(a,v)
            elif act=='loop': fn,args=ed.loop_audio,(a,v)
            elif act=='insert silence':
                at=ask_value('Insert silence','Insert at seconds:',ed.duration(a)/2,'float',0); fn,args=ed.insert_silence,(a,at,v)
            elif act=='lowpass': fn,args=ed.lowpass,(a,v)
            elif act=='highpass': fn,args=ed.highpass,(a,v)
            else: fn,args=ed.distortion,(a,v)
        elif act=='echo':
            d=ask_value('Echo','Delay seconds:',.3,'float',.02,2); k=ask_value('Echo','Strength:',.5,'float',0,.95); r=ask_value('Echo','Repeats:',3,'int',1,10)
            if None in (d,k,r): continue
            fn,args=ed.add_echo,(a,d,k,r)
        elif act=='reverse': fn,args=ed.reverse,(a,)
        elif act=='mono': fn,args=ed.to_mono,(a,)
        elif act=='stereo': fn,args=ed.to_stereo,(a,)
        elif act in ('merge after','mix over'):
            other=ask_value('Merge audio','Choose another library file ID:\n'+'\n'.join('#%s %s'%(f['file_id'],f['file_name']) for f in files),None,'int',1)
            b=safe_call(aio.load_audio_by_id,other,STATE['user']['user_id']) if other else None
            if not b: continue
            fn,args=(ed.merge,(a,b)) if act=='merge after' else (ed.mix_into,(a,b,0.0,1.0,0.0))
        else: messagebox.showwarning('Audio Lab','Unknown operation.'); continue
        try:
            new=fn(*args)
            state['undo'].append(a); state['redo'].clear(); state['audio']=new; state['saved']=False
        except Exception as exc: messagebox.showerror('Edit failed',str(exc))

def account_page():
    action=ask_value('Account','Choose CHANGE PASSWORD or DELETE ACCOUNT:','CHANGE PASSWORD')
    if not action:return
    uid=STATE['user']['user_id']
    if action.upper()=='CHANGE PASSWORD':
        old=ask_value('Current password','Current password:',None); new=ask_value('New password','New password:',None)
        if old and new:
            result=safe_call(au.change_password,uid,old,new)
            if result: messagebox.showinfo('Account',result[1])
    elif action.upper()=='DELETE ACCOUNT':
        if not messagebox.askyesno('Delete account','This permanently deletes your account, projects and library records. Continue?'): return
        password=ask_value('Confirm password','Enter password:',None)
        if password:
            result=safe_call(au.delete_account,uid,password)
            if result and result[0]: show_login()
            elif result: messagebox.showwarning('Account',result[1])

def show_project():
    STATE['page']='project'; body=app_shell('projects')
    proj=safe_call(pj.get_project,STATE['project'],STATE['user']['user_id'])
    if not proj: show_dashboard(); return
    head=tk.Frame(body,bg=COL['bg']); head.pack(fill='x',pady=(0,15))
    heading(head,'SESSION / %04d'%proj['project_id'],proj['name'],'Full multitrack workspace · audio, drums, instruments and mastering.')
    row=tk.Frame(body,bg=COL['bg']); row.pack(fill='x',pady=10)
    label(row,'TEMPO',9,COL['muted'],True).pack(side='left')
    bpm=tk.StringVar(value=str(proj['bpm'])); tk.Spinbox(row,from_=20,to=300,textvariable=bpm,width=6,bg=COL['panel2'],fg=COL['text'],relief='flat').pack(side='left',padx=8)
    def save_project_bpm():
        try: value=int(bpm.get())
        except (TypeError,ValueError): messagebox.showwarning('Tempo','Enter a whole number from 20 to 300.'); return
        if not 20 <= value <= 300: messagebox.showwarning('Tempo','BPM must be between 20 and 300.'); return
        result=safe_call(pj.set_bpm,proj['project_id'],STATE['user']['user_id'],value)
        if result: set_status(result[1]); show_project()
    button(row,'SAVE BPM',save_project_bpm).pack(side='left')
    button(row,'+ ADD TRACK',add_track_dialog,True).pack(side='right')
    tracks=safe_call(pj.list_tracks,proj['project_id']) or []
    for i,t in enumerate(tracks):
        card=panel(body,padx=15,pady=13); card.pack(fill='x',pady=5)
        label(card,t['track_name'],13,COL['text'],True).pack(side='left')
        status='%s  ·  VOL %.2f  ·  PAN %+.2f  ·  %s%s'%(t['track_type'].upper(),float(t['volume']),float(t['pan']),'MUTED ' if t.get('is_muted') else '', 'SOLO' if t.get('is_solo') else '')
        label(card,status,9,COL['muted']).pack(side='left',padx=12)
        if t['track_type']=='audio':
            button(card,'ADD CLIP',lambda x=t:add_full_clip(x)).pack(side='right',padx=3)
            button(card,'CLIPS / FX',lambda x=t:manage_clips(x)).pack(side='right',padx=3)
        elif t['track_type']=='beat': button(card,'BEAT MAKER',lambda x=t:beat_workspace(x,proj),True).pack(side='right',padx=3)
        elif t['track_type']=='instrument': button(card,'COMPOSER',lambda x=t:composer_workspace(x,proj),True).pack(side='right',padx=3)
        button(card,'TRACK SETTINGS',lambda x=t:show_track_tools(x)).pack(side='right',padx=3)
    if not tracks:
        card=panel(body,padx=24,pady=28); card.pack(fill='x'); label(card,'Your timeline is empty.',16,COL['text'],True).pack(anchor='w'); label(card,'Add audio, beat or instrument tracks to begin.',10,COL['muted']).pack(anchor='w',pady=5)
    footer=tk.Frame(body,bg=COL['bg']); footer.pack(fill='x',pady=18)
    button(footer,'← PROJECTS',show_dashboard).pack(side='left')
    button(footer,'PREVIEW MIX',lambda: safe_call(rnd.preview_project,STATE['project'],STATE['user']['user_id'])).pack(side='right',padx=4)
    button(footer,'EXPORT WAV',export_current,True).pack(side='right',padx=4)
    button(footer,'EXPORT HISTORY',export_history).pack(side='right',padx=4)

def add_track_dialog():
    name=ask_value('Add track','Track name:','New track')
    kind=ask_value('Track type','Type audio, beat, or instrument:','audio')
    if not name or not kind:return
    kind=kind.lower().strip()
    if kind not in ('audio','beat','instrument'): messagebox.showwarning('Track type','Choose audio, beat or instrument.'); return
    result=safe_call(pj.add_track,STATE['project'],STATE['user']['user_id'],name,kind)
    if result: set_status(result[1]); show_project()

def export_history():
    rows=safe_call(rnd.list_exports,STATE['project']) or []
    messagebox.showinfo('Export history','\n'.join('%s  —  %s'%(r['exported_on'],r['output_path']) for r in rows) if rows else 'No exports yet.')

def app_shell(active='projects'):
    clear_content(); f=STATE['content']; top=tk.Frame(f,bg=COL['bg']); top.pack(fill='x',padx=30,pady=(20,16))
    brand=tk.Frame(top,bg=COL['bg']); brand.pack(side='left'); label(brand,'S / S',14,COL['cyan'],True).pack(side='left'); label(brand,'  SOUNDPAD STUDIO',12,COL['text'],True).pack(side='left')
    nav=tk.Frame(top,bg=COL['bg']); nav.pack(side='right')
    for title,fn,is_active in [('PROJECTS',show_dashboard,active=='projects'),('LIBRARY',show_library,active=='library'),('AUDIO LAB',audio_lab,False),('ACCOUNT',account_page,False)]: button(nav,title,fn,is_active).pack(side='left',padx=3)
    button(nav,'LOG OUT',show_login).pack(side='left',padx=(8,0))
    tk.Frame(f,bg=COL['line'],height=1).pack(fill='x',padx=30)
    body=tk.Frame(f,bg=COL['bg']); body.pack(fill='both',expand=True,padx=30,pady=22); STATE['body']=body
    return body

def show_library():
    STATE['page']='library'; body=app_shell('library')
    heading(body,'YOUR SOUNDS','Audio library','Import, audition and manage WAV files used by your sessions.')
    row=tk.Frame(body,bg=COL['bg']); row.pack(fill='x',pady=16)
    button(row,'+ IMPORT WAV',import_wavs,True).pack(side='left')
    files=safe_call(aio.list_user_files,STATE['user']['user_id']) or []
    if not files:
        card=panel(body,padx=24,pady=25); card.pack(fill='x'); label(card,'Your library is quiet.',15,COL['text'],True).pack(anchor='w'); label(card,'Import a WAV file to get started.',10,COL['muted']).pack(anchor='w',pady=5); return
    frame=panel(body,padx=12,pady=12); frame.pack(fill='both',expand=True)
    style=ttk.Style(); style.configure('Sound.Treeview',background=COL['panel'],foreground=COL['text'],fieldbackground=COL['panel'],rowheight=34,font=FONT)
    tree=ttk.Treeview(frame,columns=('file','duration','rate','channels','depth'),show='headings',style='Sound.Treeview')
    for col,title,width in [('file','FILE',360),('duration','DURATION',100),('rate','SAMPLE RATE',120),('channels','CHANNELS',100),('depth','BIT DEPTH',90)]: tree.heading(col,text=title); tree.column(col,width=width,anchor='w' if col=='file' else 'center')
    tree.pack(fill='both',expand=True)
    for f in files: tree.insert('','end',iid=str(f['file_id']),values=(f['file_name'],'%.2f sec'%float(f['duration_sec'] or 0),'%s Hz'%f['sample_rate'],'Stereo' if f['channels']==2 else 'Mono',str(f.get('bit_depth','—'))+' bit'))
    def selected():
        sel=tree.selection()
        if not sel: messagebox.showinfo('Select file','Choose a library file first.'); return None
        return next((f for f in files if f['file_id']==int(sel[0])),None)
    def play_selected():
        f=selected()
        if f:
            full=safe_call(aio.get_audio_file,f['file_id'],STATE['user']['user_id'])
            if full and os.path.isfile(full['file_path']): safe_call(aio.play_file,full['file_path'])
            else: messagebox.showwarning('Missing file','The original WAV file is no longer at its saved path.')
    def remove_selected():
        f=selected()
        if f and messagebox.askyesno('Remove file','Remove %s from the library? The original WAV stays on disk.'%f['file_name']):
            result=safe_call(aio.remove_audio_file,f['file_id'],STATE['user']['user_id'])
            if result: set_status(result[1]); show_library()
    button(row,'PLAY SELECTED',play_selected).pack(side='right',padx=4)
    button(row,'REMOVE SELECTED',remove_selected).pack(side='right',padx=4)
