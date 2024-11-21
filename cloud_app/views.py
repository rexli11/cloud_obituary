from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required

def home_view(request):
    return render(request, 'base.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            next_url = request.POST.get('next', '')
            if next_url:
                return redirect(next_url)
            return redirect('home')
        else:
            messages.error(request, '帳號或密碼錯誤')
    
    next_url = request.GET.get('next', '')
    return render(request, 'login.html', {'next': next_url})

def logout_view(request):
    logout(request)
    return redirect('home')

@login_required(login_url='login')
def obituary_base(request):
    return render(request, 'obituary_base.html')

@login_required(login_url='login')
def create_obituary(request):
    if request.method == 'POST':
        # 處理表單提交的邏輯
        pass
    return render(request, 'obituary_maker.html')

@login_required(login_url='login')
def search_obituary(request):
    return render(request, 'search_obituary.html')
