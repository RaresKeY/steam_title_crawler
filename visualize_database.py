"""
MIT License

Copyright (c) 2024 RaresKey

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import tkinter as tk
from tkinter import ttk
import sqlite3
import webbrowser
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
import matplotlib.dates as mdates
import db_create


class SortableTreeview(ttk.Treeview):
    """A Treeview with sortable columns and sort indicators."""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.heading_col = None
        self.sort_order = False  # False for ascending, True for descending
        self.update_column_headers()

    def sort_by_column(self, column, reverse=False):
        """Sort the Treeview by a given column."""
        items = [(self.item(k)["values"], k) for k in self.get_children('')]

        def convert(value):
            """Convert values to a comparable type, if necessary."""
            try:
                if isinstance(value, str):
                    # Attempt to convert strings to numbers if possible
                    if value.replace('.', '', 1).isdigit():
                        return float(value) if '.' in value else int(value)
                    return value
                return value
            except ValueError:
                return value

        def safe_compare(val):
            """Return a comparable value for sorting."""
            value = convert(val[self['columns'].index(column)])
            # If sorting by name or any string column, ensure the value is a string
            if column == "Name":  # Replace "Name" with the actual name of the column if different
                return str(value)
            return value

        # Sort items
        try:
            items.sort(key=lambda x: safe_compare(x[0]), reverse=reverse)
        except Exception as e:
            print(f"Sorting error: {e}")

        for ix, item in enumerate(items):
            self.move(item[1], '', ix)

        self.heading_col = column
        self.sort_order = reverse
        self.update_column_headers()

    def on_heading_click(self, col):
        """Handle column header click event."""
        if self.heading_col == col:
            self.sort_by_column(col, reverse=not self.sort_order)
        else:
            self.sort_by_column(col)

    def update_column_headers(self):
        """Update column headers with sort indicators."""
        for col in self['columns']:
            if col == self.heading_col:
                arrow = '↑' if not self.sort_order else '↓'
                self.heading(col, text=col + ' ' + arrow)
            else:
                self.heading(col, text=col)


def get_table_schema(table_name):
    """Get schema of a table."""
    try:
        conn = sqlite3.connect('steam_games.db')
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        schema = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        schema = []
    finally:
        conn.close()
    return schema


def fetch_table_names():
    """Fetch all table names from the SQLite database."""
    try:
        conn = sqlite3.connect('steam_games.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        tables = []
    finally:
        conn.close()
    return [table[0] for table in tables]


def get_latest_table():
    """Get the latest table based on the date format in the table name."""
    tables = fetch_table_names()
    # Exclude non-date tables
    price_history_tables = [table for table in tables if table not in ['sqlite_sequence']]

    latest_date = None
    latest_table = None

    for table in price_history_tables:
        try:
            table_date = datetime.strptime(table, '%Y%m%d_%H%M%S')
            if latest_date is None or table_date > latest_date:
                latest_date = table_date
                latest_table = table
        except ValueError:
            continue  # Skip tables with invalid date format

    return latest_table


def fetch_data_from_db(table_name):
    """Fetch data from the specified table in the SQLite database."""
    try:
        conn = sqlite3.connect('steam_games.db')
        cursor = conn.cursor()
        cursor.execute(f'SELECT name, price, currency, url FROM "{table_name}"')
        data = cursor.fetchall()
        # Print data for debugging
        # print(data)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        data = []
    finally:
        conn.close()
    return data


def fetch_price_history(game_name):
    """Fetch price history for a given game from all tables."""
    tables = fetch_table_names()
    # Exclude sqlite_sequence table
    price_history_tables = [table for table in tables if table not in ['sqlite_sequence']]

    all_dates = []
    all_prices = []

    for table_name in price_history_tables:
        # Extract date from table name
        try:
            table_date = datetime.strptime(table_name, '%Y%m%d_%H%M%S')
        except ValueError:
            print(f"Table {table_name} has an invalid name format.")
            continue

        try:
            conn = sqlite3.connect('steam_games.db')
            cursor = conn.cursor()
            cursor.execute(f'SELECT name, price FROM "{table_name}" WHERE name=?', (game_name,))
            rows = cursor.fetchall()

            if rows:
                prices = [row[1] for row in rows]
                all_dates.extend([table_date] * len(prices))
                all_prices.extend(prices)

        except sqlite3.Error as e:
            print(f"Database error: {e}")

        finally:
            conn.close()

    return all_dates, all_prices


def on_table_select(event):
    """Load data for the selected table and populate the Treeview."""
    table_name = table_selection.get()
    if table_name:
        data = fetch_data_from_db(table_name)

        # Clear previous data
        tree.delete(*tree.get_children())

        # Insert new data
        for i, row in enumerate(data, start=1):
            # Combine price and currency into one column
            combined_price_currency = f"{row[1]} {row[2]}"
            tree.insert('', tk.END, values=(i, row[0], combined_price_currency, row[3]))

        # Show details and plot price history for the selected table
        if tree.get_children():
            tree.selection_set(tree.get_children()[0])
            on_item_select(None)


def on_item_select(event):
    """Show details of the selected item and plot price changes."""
    selected_item = tree.selection()
    if selected_item:
        item = tree.item(selected_item[0])
        game_name.set(item['values'][1])  # Name column
        game_price.set(item['values'][2])  # Combined Price and Currency
        game_url.set(item['values'][3])  # URL column

        # Fetch and plot price history
        dates, prices = fetch_price_history(item['values'][1])
        plot_price_history(dates, prices)


def open_url(event):
    """Open the URL in the web browser."""
    item = tree.identify('item', event.x, event.y)
    if item:
        url = tree.item(item)['values'][3]
        if url:
            webbrowser.open(url)


def plot_price_history(dates, prices):
    """Plot the price history using Matplotlib."""
    fig, ax = plt.subplots(figsize=(10, 6))

    if dates and prices:
        ax.plot(dates, prices, marker='o', linestyle='-')

        ax.set_xlabel('Date')
        ax.set_ylabel('Price')
        ax.set_title('Price History')
        ax.grid(True)

        # Format the x-axis to include date and time
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        ax.xaxis.set_major_locator(mdates.DayLocator())
        fig.autofmt_xdate()

    else:
        ax.text(0.5, 0.5, 'No data available', horizontalalignment='center', verticalalignment='center',
                transform=ax.transAxes, fontsize=12, color='red')

    # Clear previous canvas if any
    for widget in plot_frame.winfo_children():
        widget.destroy()

    canvas = FigureCanvasTkAgg(fig, master=plot_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)


if __name__ == '__main__':

    print('Updating DB...')
    db_create.update_db()

    print('Initializing GUI...')

    # Create the Tkinter root window
    root = tk.Tk()
    root.title("Steam Games Database Viewer")

    # Create a Frame for the Table
    frame = ttk.Frame(root)
    frame.pack(fill=tk.BOTH, expand=True)

    # Fetch and display table names
    table_names = fetch_table_names()
    table_selection = tk.StringVar()
    table_menu = ttk.Combobox(root, textvariable=table_selection, values=table_names)
    table_menu.bind('<<ComboboxSelected>>', on_table_select)
    table_menu.pack(padx=10, pady=10)

    # Create the Treeview (Table) to display the data
    tree = SortableTreeview(frame, columns=("No.", "Name", "Price & Currency", "URL"), show='headings')

    # Set column headings
    tree.heading("No.", text="No.", command=lambda: tree.on_heading_click("No."))
    tree.heading("Name", text="Name", command=lambda: tree.on_heading_click("Name"))
    tree.heading("Price & Currency", text="Price & Currency", command=lambda: tree.on_heading_click("Price & Currency"))
    tree.heading("URL", text="URL", command=lambda: tree.on_heading_click("URL"))

    tree.column("No.", width=50)
    tree.column("Name", width=150)
    tree.column("Price & Currency", width=150)
    tree.column("URL", width=200)

    tree.grid(row=0, column=0, sticky='nsew')

    # Create and place Scrollbars
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    vsb.grid(row=0, column=1, sticky='ns')
    tree.configure(yscrollcommand=vsb.set)

    hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    hsb.grid(row=1, column=0, sticky='ew')
    tree.configure(xscrollcommand=hsb.set)

    tree.configure(height=20)  # Adjust based on your requirement

    # Create Labels to show details of the selected item
    details_frame = ttk.Frame(root)
    details_frame.pack(fill=tk.X, padx=10, pady=10)

    game_name = tk.StringVar()
    game_price = tk.StringVar()
    game_url = tk.StringVar()

    tk.Label(details_frame, text="Game Name:").grid(row=0, column=0, sticky=tk.W)
    tk.Label(details_frame, textvariable=game_name).grid(row=0, column=1, sticky=tk.W)

    tk.Label(details_frame, text="Price & Currency:").grid(row=1, column=0, sticky=tk.W)
    tk.Label(details_frame, textvariable=game_price).grid(row=1, column=1, sticky=tk.W)

    tk.Label(details_frame, text="URL:").grid(row=2, column=0, sticky=tk.W)
    url_label = tk.Label(details_frame, textvariable=game_url, fg='blue', cursor="hand2", width=100)
    url_label.grid(row=2, column=1, sticky=tk.W)
    url_label.bind("<Button-1>", open_url)

    # Create Frame for Matplotlib plot
    plot_frame = ttk.Frame(root)
    plot_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Bind selection event to show details and plot price history
    tree.bind('<<TreeviewSelect>>', on_item_select)

    # Adjust grid weights
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)

    plot_frame.grid_rowconfigure(0, weight=1)
    plot_frame.grid_columnconfigure(0, weight=1)

    # Automatically select the latest table
    latest_table = get_latest_table()
    if latest_table:
        table_selection.set(latest_table)
        on_table_select(None)

    # Run the Tkinter event loop
    root.mainloop()
