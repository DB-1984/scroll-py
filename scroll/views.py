from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from .models import Entry, Label
import requests
from django.shortcuts import render
from django.contrib.auth import login
from .forms import EntryForm, SearchForm
from django.db.models import Q

@ensure_csrf_cookie # mostly covers partials not automatically sending CSRF
@login_required # <--- ESSENTIAL: Ensures request.user exists for the POST
def index(request):
    # 1. Start with all entries
    entries = Entry.objects.filter(user=request.user).order_by('-created_at')
    
    # 2. Initialize the Forms - intercept based on req type
    search_form = SearchForm(request.GET or None)
    entry_form = EntryForm(request.POST or None) # empty form instantiated in index.html if None

    # 3. Handle Search Logic (GET)
    if search_form.is_valid():
        query = search_form.cleaned_data.get('q')
        if query:
            entries = entries.filter(
                Q(body__icontains=query) | Q(label__name__icontains=query) # use 'Q' for OR
            )
            
        # If HTMX is searching, just return the list partial
        if request.headers.get('HX-Request') and request.method == 'GET':
            return render(request, 'scroll/partials/entry_list_partial.html', {'entries': entries})

    # 4. Handle Post Logic (POST)
    if request.method == 'POST' and entry_form.is_valid():
        entry = entry_form.save(commit=False)
        entry.user = request.user

        label_text = entry_form.cleaned_data.get('label_name', '').strip().lower()
        
        if label_text:
            # 2. The "Signpost" Logic: Find or create the Label object
            label_obj, _ = Label.objects.get_or_create(name=label_text)
            # 3. Manually link the ID to the Entry
            entry.label = label_obj

        entry.save()

        # fetch the database-generated 'created_at' timestamp
        entry.refresh_from_db()
        
        # If HTMX is posting, return only the new entry to be prepended
        # entry_list_partial expects an 'entries' list, and we're feeding it the new entry
        if request.headers.get('HX-Request'):
            return render(request, 'scroll/partials/entry_list_partial.html', {'entries': [entry]})
            
        return redirect('index')

    # 5. The standard page load (The "Chef" delivers the tray)
    return render(request, 'scroll/index.html', {
        'entries': entries,
        'entry_form': entry_form,
        'search_form': search_form,
    })

@login_required
def delete_entry(request, pk):
    # This filter is your 'Authorization' check
    entry = get_object_or_404(Entry, pk=pk, user=request.user)
    entry.delete()
    return HttpResponse("")

@login_required
def edit_entry(request, pk):
    entry = get_object_or_404(Entry, pk=pk)
    
    if request.method == 'POST':
        form = EntryForm(request.POST, instance=entry)
        if form.is_valid():
            # 1. Hold it in memory
            entry = form.save(commit=False) 

            # 2. String-to-Object conversion
            label_text = form.cleaned_data.get('label_name')
            if label_text:
                label_obj, _ = Label.objects.get_or_create(name=label_text)
                entry.label = label_obj
            else:
                entry.label = None # Clear it if the user deleted the text

            # 3. CRITICAL: call save() on the object now!
            entry.save() 
            
            # 4. Return the updated item to HTMX
            return render(request, 'scroll/entry_item.html', {'entry': entry})
            
    else:
        # Pre-fill for the GET request
        initial_data = {'label_name': entry.label.name if entry.label else ''}
        form = EntryForm(instance=entry, initial=initial_data)
    
    return render(request, 'scroll/partials/entry_edit_partial.html', { # update the list view item
        'entry': entry,
        'entry_form': form
    })

@login_required # <--- ADDED THIS
def get_entry(request, pk):
    # Important: Still filter by user so people can't 'peek' at others' entries
    entry = get_object_or_404(Entry, pk=pk, user=request.user)
    return render(request, 'scroll/entry_item.html', {'entry': entry})

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Log them in immediately after signing up
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def share_entry_email(request, pk):
    if request.method == "POST":
        entry = get_object_or_404(Entry, pk=pk)
        recipient = request.POST.get('email')

        if not recipient:
            return HttpResponse('<span class="text-xs text-red-500">Enter an email!</span>')
        
        # This uses your existing Resend SMTP config
        send_mail(
            subject=f"A Scroll shared by {request.user.username}",
            message=f"Check this out: {entry.body}",
            from_email="Scroll <onboarding@resend.dev>", # Must match Resend's allowed sender
            recipient_list=[recipient],
            fail_silently=False,
        )
        return HttpResponse('<span class="text-xs text-black">Sent!</span>')


@login_required
def labels_list(request):
    labels = Label.objects.filter(entries__user=request.user).distinct()
    
    return render(request, 'scroll/labels.html', {
        'labels': labels
    })

import random

@login_required
def get_weather(request):
    # 1. Configuration
    TEST_MODE = False 
    
    # 2. Logic (Get lat/lon for the is_local check)
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    is_local = lat is not None and lat != 'undefined'

    # 3. The Junction
    if TEST_MODE:
        context = {
            'temp': 30,
            'condition': 'Sun',
            'is_local': is_local
        }
    else:
        # Only attempt the "Real" world if we aren't testing
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat or 52.06}&longitude={lon or -1.33}&current_weather=true"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            current = data.get('current_weather')
            
            context = {
                'temp': round(current.get('temperature')),
                'condition': _interpret_wmo(current.get('weathercode')),
                'is_local': is_local
            }
        except Exception as e:
            print(f"Weather Error: {e}")
            context = {'temp': '--', 'condition': 'Station_Offline', 'is_local': False}

    # 4. Return the partial
    return render(request, 'scroll/partials/weather.html', context)

def get_quote(request):
    # Using the /random endpoint for more variety on refresh
    url = "https://zenquotes.io/api/random"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # ZenQuotes returns a list: [{"q": "text", "a": "author"}]
        if isinstance(data, list) and len(data) > 0:
            quote_data = data[0]
            context = {
                'quote_text': quote_data.get('q'),
                'author': quote_data.get('a')
            }
        else:
            context = {
                'quote_text': "The system is silent today.",
                'author': "Scroll"
            }
    except Exception as e:
        print(f"Quote Error: {e}")
        context = {
            'quote_text': "Connection lost. Stay in the flow.",
            'author': "System"
        }
        
    return render(request, 'scroll/partials/quote.html', context)

def _interpret_wmo(code):
    """
    Translates WMO Weather interpretation codes (WW) into Scroll-friendly strings.
    Ref: https://open-meteo.com/en/docs
    """
    mapping = {
        0: "Clear",
        1: "Mainly_Clear", 2: "Partly_Cloudy", 3: "Overcast",
        45: "Foggy", 48: "Rime_Fog",
        51: "Light_Drizzle", 53: "Drizzle", 55: "Heavy_Drizzle",
        61: "Slight_Rain", 63: "Rain", 65: "Heavy_Rain",
        71: "Slight_Snow", 73: "Snow", 75: "Heavy_Snow",
        77: "Snow_Grains",
        80: "Slight_Showers", 81: "Showers", 82: "Violent_Showers",
        95: "Thunderstorm", 96: "Thunderstorm_Hail", 99: "Thunderstorm_Heavy"
    }
    return mapping.get(code, "Unknown_System_State")