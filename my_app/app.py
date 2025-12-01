import datetime
import math
from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os
import uuid 

# --- ステップ1: 偽の期日を計算するロジック ---
def calculate_fake_deadline(real_deadline_str):
    """
    本当の期日（文字列）を受け取り、偽の期日（日付オブジェクト）を計算して返す関数
    ロジック:
    - 未来の期日: 70%ルールで「偽の期日」を計算
    - 今日または過去の期日: 「本当の期日」をそのまま返す (消さない)
    """
    try:
        real_deadline = datetime.datetime.strptime(real_deadline_str, '%Y-%m-%d').date()
    except ValueError:
        return None

    # ▼▼▼ デモ用に日付を偽装 (例: 11月18日) ▼▼▼
    # (デモが終わったら、下の行を有効にし、上の行をコメントアウトしてください)
    today = datetime.date(2025, 11, 25) 
    # today = datetime.date.today() 
    # ▲▲▲
    
    # 本当の期日までの総日数を計算
    total_days = (real_deadline - today).days
    
    if total_days > 0:
        # 1. 期日が【未来】の場合のみ、70%ルールを適用
        days_to_add = math.floor(total_days * 0.7)
        fake_deadline = today + datetime.timedelta(days=days_to_add)
        return fake_deadline
    else:
        # 2. 期日が【今日】または【過去】の場合は、
        #    「本当の期日」をそのまま「偽の期日」として返す
        return real_deadline

# --- Flaskアプリの初期化 ---
app = Flask(__name__)

# --- データの保存/読み込み関数 ---
DATA_FILE = "tasks.json"

def load_tasks_from_file():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
            return tasks
    except json.JSONDecodeError:
        return []

def save_tasks_to_file(tasks):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, indent=4, ensure_ascii=False)

# サーバー起動時に、ファイルからタスクを読み込む
tasks_db = load_tasks_from_file()

# --- トップページ (HTMLに偽の今日を渡す) ---
@app.route('/')
def index():
    """
    HTML側に「偽の今日」の日付を渡す
    """
    # ▼▼▼ デモ用偽装日付を定義 ▼▼▼
    fake_today_for_demo = datetime.date(2025, 11, 25)
    # ▲▲▲
    
    # HTMLテンプレートに、偽の日付文字列を渡す
    return render_template('index.html', fake_today_str=fake_today_for_demo.isoformat())


# --- カレンダーに表示するタスクデータをJSONで返すAPI ---
@app.route('/api/get_tasks')
def get_tasks():
    
    # ▼▼▼ デモ用に日付を偽装 (1. と同じ日付に) ▼▼▼
    # (デモが終わったら、下の行を有効にし、上の行をコメントアウトしてください)
    today = datetime.date(2025, 11, 25) 
    # today = datetime.date.today()
    # ▲▲▲
    
    calendar_events = [] 
    
    for task in tasks_db:
        
        # 1. 偽の期日(文字列) を 日付オブジェクト に変換
        fake_date_obj = None
        if task.get('fake_str'):
            try:
                fake_date_obj = datetime.date.fromisoformat(task['fake_str'])
            except (ValueError, TypeError):
                fake_date_obj = None 
        
        display_date_str = None
        is_real_deadline_showing = False # <-- 色分け用のフラグ
        
        # 2. 表示ロジック
        if fake_date_obj and today <= fake_date_obj:
            # 2a. 偽の期日が存在し、かつ「今日」が「偽の期日」*以前*の場合
            display_date_str = task['fake_str']
            is_real_deadline_showing = False # 「偽の期日」を表示中
        else:
            # 2b. それ以外 (偽の期日を過ぎた / 偽の期日がNoneだった)
            display_date_str = task.get('real_str')
            is_real_deadline_showing = True # 「本当の期日」を表示中
            
        # 3. 表示する日付 (display_date_str) が決定した場合のみ、カレンダーに追加
        if display_date_str:
            calendar_events.append({
                'id': task.get('id', ''), 
                'title': task.get('name', ' (名前なし)'),
                'start': display_date_str,
                'extendedProps': {
                    'real_str': task.get('real_str', ''),
                    'is_real_deadline_showing': is_real_deadline_showing # <-- フラグを渡す
                }
            })
            
    return jsonify(calendar_events)


# --- タスク追加 ---
@app.route('/add_task', methods=['POST'])
def add_task():
    global tasks_db
    try:
        data = request.json
        task_name = data.get('task_name')
        real_deadline_str = data.get('real_deadline')
        
        if not task_name or not real_deadline_str:
             return jsonify({'status': 'error', 'message': 'タスク名と日付は必須です'}), 400

        fake_deadline_obj = calculate_fake_deadline(real_deadline_str)
        
        fake_deadline_str = None
        if fake_deadline_obj:
            fake_deadline_str = fake_deadline_obj.isoformat()

        new_task = {
            'id': str(uuid.uuid4()), 
            'name': task_name,
            'real_str': real_deadline_str,
            'fake_str': fake_deadline_str
        }
        
        tasks_db.append(new_task)
        save_tasks_to_file(tasks_db)
        
        return jsonify({'status': 'success', 'task_name': task_name})

    except Exception as e:
        print(f"add_task エラー: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 400

# --- タスク編集/削除 (バグ修正済み) ---
@app.route('/api/update_task', methods=['POST'])
def update_task():
    global tasks_db
    try:
        data = request.json
        task_id = data.get('id')
        action = data.get('action') 

        if not task_id or not action:
            return jsonify({'status': 'error', 'message': 'IDまたはアクションがありません'}), 400
        
        if action == 'delete':
            tasks_db = [task for task in tasks_db if task.get('id') != task_id]
        
        elif action == 'edit':
            payload = data.get('payload')
            new_name = payload.get('name')
            new_date_str = payload.get('date')

            if not new_name or not new_date_str:
                return jsonify({'status': 'error', 'message': 'ペイロードが不正です'}), 400

            found = False
            for task in tasks_db:
                if task.get('id') == task_id:
                    
                    # 1. まず名前を更新
                    task['name'] = new_name
                    
                    # 2. 「本当の期日」が変更された場合 *のみ*、偽の期日を再計算
                    if new_date_str != task.get('real_str'):
                        task['real_str'] = new_date_str
                        # 偽の期日を再計算
                        new_fake_obj = calculate_fake_deadline(new_date_str)
                        task['fake_str'] = new_fake_obj.isoformat() if new_fake_obj else None
                    
                    # (もし日付が変更されていなければ、fake_str は一切触らない)
                    
                    found = True
                    break
            
            if not found:
                return jsonify({'status': 'error', 'message': 'タスクが見つかりません'}), 404
        
        else:
            return jsonify({'status': 'error', 'message': '不明なアクションです'}), 400

        save_tasks_to_file(tasks_db)
        return jsonify({'status': 'success'})

    except Exception as e:
        print(f"update_task エラー: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 400

# --- サーバー実行 ---
if __name__ == '__main__':
    app.run(debug=True)