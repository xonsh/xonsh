(function ($) {
    "use strict";

    $(document).ready(function () {

        /*---------------------------------------------------
            home carousel
        ----------------------------------------------------*/
        $('.home-carousel').owlCarousel({
            loop: true,
            autoplay: true,
            autoplayTimeout: 5000,
            smartSpeed: 450,
            responsive: {
                0: {
                    items: 1
                },
                768: {
                    items: 1
                },
                991: {
                    items: 1
                },
                1200: {
                    items: 1
                },
                1920: {
                    items: 1
                }
            }
        });

        /*---------------------------------------------------
            about Carousel
        ----------------------------------------------------*/
        $('.testi-carousel').owlCarousel({
            loop: true,
            responsive: {
                0: {
                    items: 1
                },
                768: {
                    items: 2
                },
                991: {
                    items: 3
                },
                1200: {
                    items: 3
                },
                1920: {
                    items: 3
                }
            }
        });

        /*---------------------------------------------------
                PopUp video
        ----------------------------------------------------*/
        $('.popup-video').magnificPopup({
            disableOn: 700,
            type: 'iframe',
            mainClass: 'mfp-fade',
            removalDelay: 160,
            preloader: false,
            fixedContentPos: false,
            disableOn: 300
        });

        /*---------------------------------------------------
            accordian
        ----------------------------------------------------*/
        $('.collapse').on('shown.bs.collapse', function () {
            $(this).prev().addClass('active');
        });

        $('.collapse').on('hidden.bs.collapse', function () {
            $(this).prev().removeClass('active');
        });

        /*---------------------------------------------------
            scrollIt plugin activation
        ----------------------------------------------------*/
        $.scrollIt();

    });

    /*---------------------------------------------------
        smooth scroll
    ----------------------------------------------------*/
    $('a[href*="#"]:not([href="#"]):not([data-toggle])').on('click', function () {
        if (location.pathname.replace(/^\//, '') == this.pathname.replace(/^\//, '') && location.hostname == this.hostname) {
            var target = $(this.hash);
            target = target.length ? target : $('[name=' + this.hash.slice(1) + ']');
            if (target.length) {
                $('html, body').animate({
                    scrollTop: target.offset().top
                }, 1000);
                return false;
            }
        }
    });

    /*---------------------------------------------------
        sticky header
    ----------------------------------------------------*/
    $(window).on('scroll', function () {
        var scroll = $(window).scrollTop();
        if (scroll < 100) {
            $("#header").removeClass("sticky");
        } else {
            $("#header").addClass("sticky");
        }
    });

    /*---------------------------------------------------
        preloader
    ----------------------------------------------------*/
    $(window).on('load', function () {
        $('.preloader').fadeOut(500);
    });


}(jQuery));
